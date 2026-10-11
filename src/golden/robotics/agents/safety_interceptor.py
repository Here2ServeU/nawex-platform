"""Deterministic safety interceptor for clinical robotics telemetry.

Evaluates each telemetry packet against the bundled ``failover_policy.json`` and returns the
strongest required intervention. Deterministic by design: safety-critical decisions are never
delegated to a learned model.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from importlib import resources
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Higher number = stronger intervention.
ACTION_PRIORITY = {
    "NOMINAL": 0,
    "ENABLE_LOCAL_PERSISTENCE": 1,
    "REROUTE_TO_EDGE": 2,
    "SAFE_STATE_TRANSITION": 3,
    "EMERGENCY_STOP": 4,
}


@dataclass(frozen=True)
class Intervention:
    action: str
    reasons: tuple[str, ...]
    incident_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_policy(path: str | Path | None = None) -> dict[str, Any]:
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    text = resources.files("golden.robotics.agents").joinpath("failover_policy.json").read_text("utf-8")
    return json.loads(text)


class SafetyInterceptor:
    def __init__(self, policy: dict[str, Any] | None = None, incident_dir: str | Path | None = None) -> None:
        self.policy = policy or load_policy()
        self.incident_dir = Path(incident_dir) if incident_dir else None
        self.failover_active = False
        self.incidents: list[dict[str, Any]] = []

    def analyze_telemetry(self, packet: dict[str, Any]) -> Intervention:
        t = self.policy.get("thresholds", {})
        telemetry = packet.get("telemetry", {})
        net, kin = telemetry.get("network", {}), telemetry.get("kinematics", {})
        triggered: list[tuple[str, str]] = []

        rtt = float(net.get("cloud_rtt_ms", 0) or 0)
        if rtt > t.get("network_latency", {}).get("critical_ms", 25.0):
            triggered.append((t.get("network_latency", {}).get("action", "REROUTE_TO_EDGE"), f"RTT {rtt}ms"))

        stab = t.get("kinematic_stability", {})
        vib = float(kin.get("joint_vibration_index", 0) or 0)
        if vib > stab.get("max_vibration_index", 0.05):
            triggered.append((stab.get("action", "SAFE_STATE_TRANSITION"), f"vibration {vib}"))
        temp = float(kin.get("motor_temp_celsius", 0) or 0)
        if temp > stab.get("thermal_limit_celsius", 42.0):
            triggered.append((stab.get("action", "SAFE_STATE_TRANSITION"), f"motor temp {temp}°C"))

        loss = float(net.get("packet_loss", net.get("packet_loss_pct", 0)) or 0)
        if loss > t.get("packet_reliability", {}).get("max_loss_pct", 0.01):
            triggered.append(
                (
                    t.get("packet_reliability", {}).get("action", "ENABLE_LOCAL_PERSISTENCE"),
                    f"packet loss {loss}",
                )
            )

        if not triggered:
            return Intervention("NOMINAL", ())
        action = max((a for a, _ in triggered), key=lambda a: ACTION_PRIORITY.get(a, 0))
        reasons = tuple(r for _, r in triggered)
        incident_id = self._record_incident(packet.get("device_id", "unknown"), action, reasons)
        self.failover_active = True
        return Intervention(action, reasons, incident_id)

    def _record_incident(self, device: str, action: str, reasons: tuple[str, ...]) -> str:
        report = {
            "incident_id": f"INC-{time.time_ns()}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "device_id": device,
            "policy_applied": self.policy.get("policy_name"),
            "intervention": action,
            "root_cause_analysis": list(reasons),
            "compliance": self.policy.get("governance", {}).get("compliance_standard"),
        }
        self.incidents.append(report)
        if self.incident_dir:
            self.incident_dir.mkdir(parents=True, exist_ok=True)
            (self.incident_dir / f"{report['incident_id']}.json").write_text(json.dumps(report, indent=2))
        logger.warning("robotics intervention", extra={"action": action, "device": device})
        return str(report["incident_id"])
