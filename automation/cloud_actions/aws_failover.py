"""AWS failover placeholder action."""


def run_failover(service: str) -> str:
    return f"failover_triggered:{service}"
