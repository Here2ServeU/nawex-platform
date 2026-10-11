"""Action governor — the single gate every autonomous action must pass.

Controls, applied in order:

1. **Kill switch**   — engaged ⇒ nothing executes.
2. **Allowlist**     — only actions in :data:`ACTION_CATALOG` exist; anything else is denied.
3. **Blast radius**  — an action may touch at most ``max_targets`` resources.
4. **Rate caps**     — global actions/hour (``GOLDEN_MAX_ACTIONS_PER_HOUR``) and per-action/hour.
5. **Autonomy mode** — ``dry_run`` simulates; ``supervised`` runs low-risk only; ``autonomous`` runs
   low/high-risk; **critical actions always require a named human approver**.

Every verdict is written to the tamper-evident audit log.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from golden.config import AutonomyMode, get_settings
from golden.security import killswitch
from golden.security.audit import AuditLog, default_audit_log
from golden.security.metrics import ACTIONS_BLOCKED, ACTIONS_EXECUTED


class Risk(StrEnum):
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"


class Outcome(StrEnum):
    EXECUTE = "execute"
    SIMULATE = "simulate"
    PENDING_APPROVAL = "pending_approval"
    BLOCKED = "blocked"


ACTION_CATALOG: dict[str, Risk] = {
    # platform / SRE
    "scale_up_replicas": Risk.LOW,
    "optimize_resources": Risk.LOW,
    "throttle_api_clients": Risk.LOW,
    "restart_service": Risk.HIGH,
    # fintech
    "failover_payment_gateway": Risk.HIGH,
    "isolate_fraud_transactions": Risk.CRITICAL,
    "halt_settlement": Risk.CRITICAL,
    # healthcare
    "failover_ehr_gateway": Risk.HIGH,
    "isolate_phi_breach": Risk.CRITICAL,
    "halt_clinical_pipeline": Risk.CRITICAL,
    "quarantine_patient_data": Risk.CRITICAL,
    # GPU / AI infrastructure
    "set_gpu_power_cap": Risk.LOW,
    "reclaim_idle_gpus": Risk.LOW,
    "consolidate_gpu_workloads": Risk.HIGH,
    "migrate_gpu_workload": Risk.HIGH,
    "drain_gpu_node": Risk.HIGH,
    # VMware -> OpenShift migration
    "start_vm_migration": Risk.CRITICAL,
    "vm_cutover": Risk.CRITICAL,
    "vm_rollback": Risk.CRITICAL,
}


@dataclass(frozen=True)
class Verdict:
    request_id: str
    action: str
    risk: Risk | None
    outcome: Outcome
    reason: str
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def may_execute(self) -> bool:
        return self.outcome is Outcome.EXECUTE


class ActionGovernor:
    def __init__(
        self,
        *,
        max_actions_per_hour: int | None = None,
        max_per_action_per_hour: int = 5,
        max_targets: int = 5,
        audit: AuditLog | None = None,
        clock: Any = time.monotonic,
    ) -> None:
        self._max_per_hour = max_actions_per_hour
        self.max_per_action_per_hour = max_per_action_per_hour
        self.max_targets = max_targets
        self.audit = audit or default_audit_log()
        self._clock = clock
        self._history: deque[tuple[float, str]] = deque()
        self._pending: dict[str, Verdict] = {}
        self._lock = threading.Lock()

    @property
    def max_actions_per_hour(self) -> int:
        return self._max_per_hour if self._max_per_hour is not None else get_settings().max_actions_per_hour

    # ------------------------------------------------------------------ internals
    def _prune(self, now: float) -> None:
        while self._history and now - self._history[0][0] > 3600:
            self._history.popleft()

    def _block(self, request_id: str, action: str, risk: Risk | None, reason: str, params: dict) -> Verdict:
        ACTIONS_BLOCKED.labels(reason=reason).inc()
        return Verdict(request_id, action, risk, Outcome.BLOCKED, reason, params)

    def usage(self) -> dict[str, int]:
        with self._lock:
            self._prune(self._clock())
            return {"actions_last_hour": len(self._history), "cap": self.max_actions_per_hour}

    # ------------------------------------------------------------------ public API
    def evaluate(
        self, action: str, params: dict[str, Any] | None = None, *, actor: str = "planner"
    ) -> Verdict:
        params = dict(params or {})
        request_id = uuid.uuid4().hex[:12]
        risk = ACTION_CATALOG.get(action)
        settings = get_settings()

        with self._lock:
            now = self._clock()
            self._prune(now)
            targets = params.get("targets")
            n_targets = len(targets) if isinstance(targets, list | tuple) else 1

            if killswitch.is_engaged():
                verdict = self._block(request_id, action, risk, "kill_switch", params)
            elif risk is None:
                verdict = self._block(request_id, action, risk, "not_allowlisted", params)
            elif n_targets > self.max_targets:
                verdict = self._block(request_id, action, risk, "blast_radius", params)
            elif len(self._history) >= self.max_actions_per_hour:
                verdict = self._block(request_id, action, risk, "global_rate_cap", params)
            elif sum(1 for _, a in self._history if a == action) >= self.max_per_action_per_hour:
                verdict = self._block(request_id, action, risk, "action_rate_cap", params)
            elif settings.autonomy_mode is AutonomyMode.DRY_RUN:
                verdict = Verdict(request_id, action, risk, Outcome.SIMULATE, "dry_run_mode", params)
            elif risk is Risk.CRITICAL or (
                risk is Risk.HIGH and settings.autonomy_mode is AutonomyMode.SUPERVISED
            ):
                verdict = Verdict(
                    request_id, action, risk, Outcome.PENDING_APPROVAL, "human_approval_required", params
                )
                self._pending[request_id] = verdict
            else:
                verdict = Verdict(request_id, action, risk, Outcome.EXECUTE, "within_policy", params)
                self._history.append((now, action))
                ACTIONS_EXECUTED.labels(action=action, mode=settings.autonomy_mode.value).inc()

        self.audit.record(
            "action.verdict",
            {
                "request_id": request_id,
                "action": action,
                "risk": risk,
                "outcome": verdict.outcome,
                "reason": verdict.reason,
                "params": params,
            },
            actor=actor,
        )
        return verdict

    def pending(self) -> list[Verdict]:
        with self._lock:
            return list(self._pending.values())

    def approve(self, request_id: str, approver: str) -> Verdict:
        """Release a pending action. Caps and the kill switch are re-checked at approval time."""
        if not approver or approver == "system":
            raise PermissionError("approval requires a named human approver")
        with self._lock:
            original = self._pending.pop(request_id, None)
        if original is None:
            raise KeyError(f"no pending action {request_id}")
        with self._lock:
            now = self._clock()
            self._prune(now)
            if killswitch.is_engaged():
                verdict = self._block(
                    request_id, original.action, original.risk, "kill_switch", original.params
                )
            elif len(self._history) >= self.max_actions_per_hour:
                verdict = self._block(
                    request_id, original.action, original.risk, "global_rate_cap", original.params
                )
            else:
                verdict = Verdict(
                    request_id,
                    original.action,
                    original.risk,
                    Outcome.EXECUTE,
                    f"approved_by:{approver}",
                    original.params,
                )
                self._history.append((now, original.action))
                ACTIONS_EXECUTED.labels(action=original.action, mode="approved").inc()
        self.audit.record(
            "action.approval",
            {"request_id": request_id, "action": original.action, "outcome": verdict.outcome},
            actor=approver,
        )
        return verdict

    def reject(self, request_id: str, approver: str) -> None:
        with self._lock:
            original = self._pending.pop(request_id, None)
        if original is None:
            raise KeyError(f"no pending action {request_id}")
        self.audit.record(
            "action.rejected", {"request_id": request_id, "action": original.action}, actor=approver
        )


_default_governor: ActionGovernor | None = None


def default_governor() -> ActionGovernor:
    global _default_governor
    if _default_governor is None:
        _default_governor = ActionGovernor()
    return _default_governor


def security_status() -> dict[str, Any]:
    settings = get_settings()
    governor = default_governor()
    return {
        "autonomy_mode": settings.autonomy_mode.value,
        "kill_switch_engaged": killswitch.is_engaged(),
        "auth_enabled": settings.auth_enabled,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        **governor.usage(),
        "pending_approvals": len(governor.pending()),
        "audit_chain_valid": governor.audit.verify(),
    }
