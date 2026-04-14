"""Metrics ingestion placeholder for canonical NAWEX structure."""


def ingest_metrics(payload: dict) -> dict:
    return {"status": "accepted", "type": "metrics", "size": len(payload)}
