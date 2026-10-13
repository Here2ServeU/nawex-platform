"""Remediation engine — maps approved actions to handlers.

Handlers here are *simulated integrations*: each logs exactly what a production integration
(Kubernetes API, payment switch, vCenter / MTV, NVIDIA DCGM) would do. Swap a handler for a real client
without touching the governance path: actions only reach :func:`execute_action` after the
:class:`~golden.security.actions.ActionGovernor` has allowed them.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from importlib import resources
from typing import Any

import yaml

from golden.config import get_settings

logger = logging.getLogger(__name__)

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def load_rules() -> dict[str, Any]:
    """Load the risk → action rules bundled with the package."""
    try:
        text = resources.files("golden.ai.remediation").joinpath("remediation_rules.yaml").read_text("utf-8")
        data = yaml.safe_load(text) or {}
        return {"rules": list(data.get("rules", []))}
    except (OSError, yaml.YAMLError):
        logger.exception("failed to load remediation rules")
        return {"rules": []}


def _pause() -> None:
    delay = get_settings().simulation_delay_seconds
    if delay:
        time.sleep(delay)


def _step(action: str, message: str, **fields: Any) -> None:
    logger.info(message, extra={"action": action, **fields})


def _scale(p: dict) -> dict:
    target, replicas = p.get("target", "critical-microservice"), int(p.get("replicas", 4))
    _step("scale_up_replicas", f"scaling deployment {target} to {replicas} replicas", target=target)
    _pause()
    return {"target": target, "replicas": replicas}


def _restart(p: dict) -> dict:
    target = p.get("target", "backend-api")
    _step("restart_service", f"rolling restart of {target}", target=target)
    _pause()
    return {"target": target, "strategy": p.get("strategy", "rolling_update")}


def _optimize(p: dict) -> dict:
    _step("optimize_resources", "right-sizing requests/limits from observed usage", target=p.get("target"))
    return {"target": p.get("target"), "cpu_limit": p.get("cpu_limit")}


def _throttle(p: dict) -> dict:
    pct = int(p.get("throttle_percent", 50))
    _step("throttle_api_clients", f"throttling non-allowlisted clients by {pct}%", target=p.get("target"))
    return {"throttle_percent": pct, "allowlist": p.get("allowlist", [])}


def _isolate_fraud(p: dict) -> dict:
    threshold = float(p.get("block_threshold", 0.9))
    _step("isolate_fraud_transactions", f"blocking transactions with fraud score > {threshold}")
    _pause()
    return {"block_threshold": threshold, "notified": p.get("notify", "fraud-ops-team")}


def _failover(kind: str) -> Handler:
    def handler(p: dict) -> dict:
        primary = p.get("primary", f"{kind}-primary")
        secondary = p.get("secondary", f"{kind}-secondary")
        _step(f"failover_{kind}", f"failing over {primary} -> {secondary}; in-flight work preserved in queue")
        _pause()
        return {"primary": secondary, "previous_primary": primary}

    return handler


def _halt(kind: str) -> Handler:
    def handler(p: dict) -> dict:
        target = p.get("target", kind)
        _step(f"halt_{kind}", f"halting {target} at a checkpoint; notifying {p.get('notify', 'ops')}")
        _pause()
        return {"target": target, "checkpointed": bool(p.get("checkpoint", True))}

    return handler


def _isolate_phi(p: dict) -> dict:
    _step("isolate_phi_breach", "isolating PHI flows, locking sessions, preserving HIPAA audit trail")
    _pause()
    return {"sessions_locked": bool(p.get("lock_user_sessions", True)), "breach_clock_started": True}


def _quarantine(p: dict) -> dict:
    scope = p.get("quarantine_scope", "affected_patient")
    _step("quarantine_patient_data", f"quarantining records (scope={scope}); clinician override required")
    return {"scope": scope, "requires_override": bool(p.get("require_clinician_override", True))}


def _gpu_power_cap(p: dict) -> dict:
    cap = int(p.get("cap_pct_of_tdp", 80))
    _step("set_gpu_power_cap", f"nvidia-smi -pl → {cap}% of TDP", node=p.get("node"))
    return {"cap_pct_of_tdp": cap, "node": p.get("node")}


def _gpu_reclaim(p: dict) -> dict:
    gpus = p.get("targets", [])
    _step("reclaim_idle_gpus", f"returning {len(gpus)} idle GPUs to the shared pool")
    return {"reclaimed": gpus}


def _gpu_consolidate(p: dict) -> dict:
    _step("consolidate_gpu_workloads", "bin-packing workloads onto fewer nodes / MIG slices")
    _pause()
    return {"target_utilization_pct": int(p.get("target_utilization_pct", 70))}


def _gpu_migrate(p: dict) -> dict:
    _step("migrate_gpu_workload", f"checkpointing and rescheduling job off {p.get('node', 'hot node')}")
    _pause()
    return {"node": p.get("node"), "cordoned": bool(p.get("cordon_source_node", True))}


def _gpu_drain(p: dict) -> dict:
    _step("drain_gpu_node", f"cordon + drain {p.get('node', 'node')} for hardware triage")
    return {"node": p.get("node"), "drained": True}


def _vm_migrate(p: dict) -> dict:
    _step("start_vm_migration", f"creating MTV Migration for plan {p.get('plan', 'wave')}")
    _pause()
    return {"plan": p.get("plan"), "vms": p.get("targets", [])}


def _vm_cutover(p: dict) -> dict:
    _step(
        "vm_cutover", f"cutover for plan {p.get('plan', 'wave')}: final sync, power off source, start target"
    )
    _pause()
    return {"plan": p.get("plan"), "cutover": True}


def _vm_rollback(p: dict) -> dict:
    _step(
        "vm_rollback", f"rolling back plan {p.get('plan', 'wave')}: stop target VMs, power on vSphere source"
    )
    _pause()
    return {"plan": p.get("plan"), "source_powered_on": bool(p.get("power_on_source", True))}


def _iam_quarantine(p: dict) -> dict:
    _step("quarantine_iam_role", f"attaching deny-all policy and pinning trust on {p.get('role', 'role')}")
    _pause()
    return {"role": p.get("role"), "account_id": p.get("account_id"), "quarantined": True}


def _iam_delete(p: dict) -> dict:
    _step("delete_iam_role", f"deleting unused role {p.get('role', 'role')} after owner sign-off")
    _pause()
    return {"role": p.get("role"), "account_id": p.get("account_id"), "deleted": True}


HANDLERS: dict[str, Handler] = {
    "scale_up_replicas": _scale,
    "restart_service": _restart,
    "optimize_resources": _optimize,
    "throttle_api_clients": _throttle,
    "isolate_fraud_transactions": _isolate_fraud,
    "failover_payment_gateway": _failover("payment_gateway"),
    "halt_settlement": _halt("settlement"),
    "isolate_phi_breach": _isolate_phi,
    "failover_ehr_gateway": _failover("ehr_gateway"),
    "halt_clinical_pipeline": _halt("clinical_pipeline"),
    "quarantine_patient_data": _quarantine,
    "set_gpu_power_cap": _gpu_power_cap,
    "reclaim_idle_gpus": _gpu_reclaim,
    "consolidate_gpu_workloads": _gpu_consolidate,
    "migrate_gpu_workload": _gpu_migrate,
    "drain_gpu_node": _gpu_drain,
    "start_vm_migration": _vm_migrate,
    "vm_cutover": _vm_cutover,
    "vm_rollback": _vm_rollback,
    "quarantine_iam_role": _iam_quarantine,
    "delete_iam_role": _iam_delete,
}


def execute_action(action: str | dict[str, Any]) -> bool:
    """Run one remediation action. Returns ``True`` on success, ``False`` for unknown/failed actions."""
    if isinstance(action, str):
        name, params = action, {}
    else:
        name, params = str(action.get("action", "unknown")), dict(action.get("params", {}))
    handler = HANDLERS.get(name)
    if handler is None:
        logger.warning("unknown remediation action %s; skipping", name)
        return False
    try:
        handler(params)
        return True
    except Exception:
        logger.exception("remediation action %s failed", name)
        return False
