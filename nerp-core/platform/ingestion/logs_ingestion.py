"""Logs ingestion placeholder for canonical NERP structure."""


def ingest_logs(payload: dict) -> dict:
    return {"status": "accepted", "type": "logs", "size": len(payload)}
