"""Decision router translating risk to action."""


def route_decision(risk_level: str) -> str:
    mapping = {
        "high": "trigger_failover",
        "medium": "scale_service",
        "low": "observe",
    }
    return mapping.get(risk_level, "escalate_incident")
