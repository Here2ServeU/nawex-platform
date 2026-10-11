"""Risk and severity bands shared by every domain."""

from __future__ import annotations

from golden.security.guardrails import clamp_score


def evaluate_risk(score: float) -> str:
    """Map a ``[0, 1]`` risk score to ``low | medium | high | critical``."""
    score = clamp_score(score)
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def evaluate_severity(risk_level: str, criticality: str = "medium") -> str:
    """Combine risk with business criticality into an incident severity (SEV1 is worst)."""
    risk_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}.get(risk_level, 1)
    crit_rank = {"low": 0, "medium": 1, "high": 2, "mission_critical": 3}.get(criticality, 1)
    combined = risk_rank + (1 if crit_rank >= 2 else 0) - (1 if crit_rank == 0 else 0)
    return {0: "SEV4", 1: "SEV3", 2: "SEV2"}.get(max(combined, 0), "SEV1")
