"""Decision engine: signal → incident class → risk/severity → recommended action → governed verdict.

The engine never executes anything itself. It returns the recommended action together with the
:class:`~golden.security.actions.ActionGovernor` verdict (execute / simulate / pending approval /
blocked), so callers and auditors see exactly why an action would or would not run.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from golden.ai.classification import classify_incident
from golden.decision.rules import evaluate_risk, evaluate_severity
from golden.security.actions import ActionGovernor, default_governor

# incident class -> (domain trigger used by remediation rules, recommended action)
ROUTES: dict[str, tuple[str, str]] = {
    "security.phi_breach": ("phi_breach_detected", "isolate_phi_breach"),
    "security.fraud": ("fraud_spike", "isolate_fraud_transactions"),
    "reliability.critical_outage": ("error_risk", "restart_service"),
    "reliability.degradation": ("latency_risk", "scale_up_replicas"),
    "gpu.thermal": ("gpu_thermal_risk", "migrate_gpu_workload"),
    "gpu.hardware": ("gpu_hardware_risk", "drain_gpu_node"),
    "gpu.efficiency": ("gpu_efficiency_risk", "consolidate_gpu_workloads"),
    "migration.validation_failure": ("migration_validation_failure", "vm_rollback"),
}


@dataclass
class Decision:
    decision_id: str
    timestamp: str
    incident_class: str
    risk_score: float
    risk_level: str
    severity: str
    recommended_action: str | None
    outcome: str
    outcome_reason: str
    request_id: str | None
    rationale: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _risk_score(signal: dict[str, Any]) -> float:
    candidates = [
        float(signal.get(k, 0.0) or 0.0)
        for k in ("risk_score", "fraud_score", "phi_anomaly_score", "clinical_risk_score", "gpu_risk_score")
    ]
    latency, slo = float(signal.get("latency_ms", 0) or 0), float(signal.get("slo_ms", 200) or 200)
    if latency:
        candidates.append(min(latency / (2 * slo), 1.0))
    return max(candidates) if candidates else 0.0


class DecisionEngine:
    def __init__(self, governor: ActionGovernor | None = None, max_history: int = 1000) -> None:
        self.governor = governor or default_governor()
        self._history: list[Decision] = []
        self._max_history = max_history
        self._lock = threading.Lock()

    def decide(self, signal: dict[str, Any], *, actor: str = "decision-engine") -> Decision:
        incident = classify_incident(signal)
        score = _risk_score(signal)
        level = evaluate_risk(score)
        severity = evaluate_severity(level, str(signal.get("criticality", "medium")))
        rationale = [f"classified as {incident}", f"risk {score:.2f} → {level}", f"severity {severity}"]

        action = None
        if incident in ROUTES and level in {"high", "critical"}:
            action = ROUTES[incident][1]
        elif level in {"high", "critical"} and incident.startswith("reliability"):
            action = "scale_up_replicas"

        if action is None:
            outcome, reason, request_id = "no_action", "below_action_threshold_or_unrouted", None
            rationale.append("no automated action; observe and record")
        else:
            params = {k: v for k, v in signal.items() if k in {"target", "targets", "node", "plan"}}
            verdict = self.governor.evaluate(action, params, actor=actor)
            outcome, reason, request_id = verdict.outcome.value, verdict.reason, verdict.request_id
            rationale.append(f"recommend {action}; governor: {outcome} ({reason})")

        decision = Decision(
            decision_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(UTC).isoformat(),
            incident_class=incident,
            risk_score=round(score, 4),
            risk_level=level,
            severity=severity,
            recommended_action=action,
            outcome=outcome,
            outcome_reason=reason,
            request_id=request_id,
            rationale=rationale,
        )
        with self._lock:
            self._history.append(decision)
            del self._history[: -self._max_history]
        return decision

    def history(self, limit: int = 100) -> list[Decision]:
        with self._lock:
            return list(reversed(self._history[-limit:]))
