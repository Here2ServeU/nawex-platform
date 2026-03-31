"""Rule-driven incident classifier used by planner-friendly workflows."""

from __future__ import annotations

from typing import Dict, Any


def classify_incident(signal: Dict[str, Any]) -> str:
    """Map a telemetry signal to an incident class label.

    Priority order:
    1. Explicit class provided by upstream systems.
    2. Safety/security conditions.
    3. Latency and reliability degradation.
    4. Fallback to generic operations incident.
    """
    if not signal:
        return "unknown"

    explicit = signal.get("class")
    if explicit:
        return str(explicit)

    fraud_score = float(signal.get("fraud_score", 0.0) or 0.0)
    phi_score = float(signal.get("phi_anomaly_score", 0.0) or 0.0)
    error_rate = float(signal.get("error_rate_percent", 0.0) or 0.0)
    latency = float(signal.get("latency_ms", 0.0) or 0.0)

    if phi_score >= 0.7:
        return "security.phi_breach"
    if fraud_score >= 0.85:
        return "security.fraud"
    if latency >= 500 or error_rate >= 5.0:
        return "reliability.critical_outage"
    if latency >= 250 or error_rate >= 1.0:
        return "reliability.degradation"

    return "operations.investigate"
