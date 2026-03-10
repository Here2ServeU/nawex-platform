"""Kafka consumer placeholder."""


def consume(topic: str) -> list[dict]:
    return [{"topic": topic, "event": "noop"}]
