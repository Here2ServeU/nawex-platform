"""Logs ingestion placeholder for canonical NAWEX structure."""


def ingest_logs(payload: dict) -> dict:
    return {"status": "accepted", "type": "logs", "size": len(payload)}
