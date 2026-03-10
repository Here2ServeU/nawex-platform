"""Risk rule definitions."""


def evaluate_risk(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"
