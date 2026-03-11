"""Kubernetes pod restart placeholder."""


def restart_pod(name: str, namespace: str) -> str:
    return f"restarted:{namespace}/{name}"
