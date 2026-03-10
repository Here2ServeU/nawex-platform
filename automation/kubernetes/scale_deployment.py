"""Kubernetes deployment scale placeholder."""


def scale_deployment(name: str, namespace: str, replicas: int) -> str:
    return f"scaled:{namespace}/{name}:{replicas}"
