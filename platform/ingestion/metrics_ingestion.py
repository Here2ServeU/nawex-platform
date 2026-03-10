"""Metrics ingestion placeholder for canonical NERP structure."""


def ingest_metrics(payload: dict) -> dict:
    return {"status": "accepted", "type": "metrics", "size": len(payload)}
