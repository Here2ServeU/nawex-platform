"""Severity rule definitions."""


def evaluate_severity(impact: float) -> str:
    if impact >= 0.8:
        return "critical"
    if impact >= 0.5:
        return "major"
    return "minor"
