"""Incident classifier placeholder."""


def classify_incident(signal: dict) -> str:
    return signal.get("class", "unknown")
