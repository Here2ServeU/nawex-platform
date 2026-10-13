"""Rule-driven incident classifier shared by the decision engine and agents."""

from __future__ import annotations

from typing import Any


def classify_incident(signal: dict[str, Any]) -> str:
    """Map a telemetry signal to an incident class.

    Priority: explicit class → security → GPU hardware/thermal → reliability → efficiency → generic.
    """
    if not signal:
        return "unknown"
    explicit = signal.get("class") or signal.get("incident_class")
    if explicit:
        return str(explicit)

    def num(key: str) -> float:
        try:
            return float(signal.get(key, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    if num("phi_anomaly_score") >= 0.7:
        return "security.phi_breach"
    if num("fraud_score") >= 0.85:
        return "security.fraud"
    if num("ecc_errors") > 0 or num("xid_errors") > 0:
        return "gpu.hardware"
    if num("gpu_temperature_c") >= 85:
        return "gpu.thermal"
    if signal.get("migration_validation") == "failed":
        return "migration.validation_failure"
    latency, error_rate = num("latency_ms"), num("error_rate_percent")
    if latency >= 500 or error_rate >= 5.0:
        return "reliability.critical_outage"
    if latency >= 250 or error_rate >= 1.0:
        return "reliability.degradation"
    if "gpu_utilization_pct" in signal and num("gpu_utilization_pct") < 30:
        return "gpu.efficiency"
    return "operations.investigate"
