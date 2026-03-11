"""Azure scale placeholder action."""


def run_scale(resource: str, replicas: int) -> str:
    return f"scaled:{resource}:{replicas}"
