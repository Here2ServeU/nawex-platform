"""
Observability — Structured Log Pipeline

Provides a lightweight log ingestion pipeline that:
  - Parses and validates incoming structured log records
  - Enriches records with platform-level labels
  - Redacts PHI fields for healthcare logs
  - Routes records to the correct Loki stream based on vertical/service
  - Ships batches to Loki via the push API
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from golden.security.redaction import redact_text

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
LOKI_PUSH_URL = os.getenv("LOKI_PUSH_URL", "http://loki:3100/loki/api/v1/push")
PLATFORM_LABEL = os.getenv("GOLDEN_PLATFORM_LABEL", "golden")
ENVIRONMENT = os.getenv("GOLDEN_ENV", "production")


class Vertical(StrEnum):
    FINTECH = "fintech"
    HEALTHCARE = "healthcare"
    ROBOTICS = "robotics"
    GPU = "gpu"
    MIGRATION = "migration"
    CORE = "core"
    UNKNOWN = "unknown"


# ── Data Models ───────────────────────────────────────────────────────────────
@dataclass
class LogRecord:
    message: str
    level: str = "INFO"
    service: str = "unknown"
    vertical: Vertical = Vertical.UNKNOWN
    trace_id: str = ""
    span_id: str = ""
    timestamp_ns: int = field(default_factory=lambda: int(time.time_ns()))
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> LogRecord:
        """Parse a flat dict (e.g. from a JSON log line) into a LogRecord."""
        vertical_raw = data.get("vertical", data.get("service", "")).lower()
        vertical = _detect_vertical(vertical_raw)
        return cls(
            message=str(data.get("message", data.get("msg", ""))),
            level=str(data.get("level", "INFO")).upper(),
            service=str(data.get("service", data.get("job", "unknown"))),
            vertical=vertical,
            trace_id=str(data.get("traceID", data.get("trace_id", ""))),
            span_id=str(data.get("spanID", data.get("span_id", ""))),
            timestamp_ns=int(data.get("timestamp_ns", int(time.time_ns()))),
            extra={
                k: v
                for k, v in data.items()
                if k
                not in {
                    "message",
                    "msg",
                    "level",
                    "service",
                    "job",
                    "vertical",
                    "traceID",
                    "trace_id",
                    "spanID",
                    "span_id",
                    "timestamp_ns",
                }
            },
        )


# ── Vertical Detection ────────────────────────────────────────────────────────
_VERTICAL_PREFIXES: dict[str, Vertical] = {
    "fintech": Vertical.FINTECH,
    "transaction": Vertical.FINTECH,
    "fraud": Vertical.FINTECH,
    "payment": Vertical.FINTECH,
    "settlement": Vertical.FINTECH,
    "healthcare": Vertical.HEALTHCARE,
    "ehr": Vertical.HEALTHCARE,
    "clinical": Vertical.HEALTHCARE,
    "patient": Vertical.HEALTHCARE,
    "robotics": Vertical.ROBOTICS,
    "surgical": Vertical.ROBOTICS,
    "gpu": Vertical.GPU,
    "migration": Vertical.MIGRATION,
    "api": Vertical.CORE,
}


def _detect_vertical(text: str) -> Vertical:
    for prefix, vertical in _VERTICAL_PREFIXES.items():
        if text.startswith(prefix):
            return vertical
    return Vertical.UNKNOWN


# ── PHI Redaction ─────────────────────────────────────────────────────────────
def redact_phi(message: str) -> str:
    """Redact PHI/PII (identifiers, SSNs, card numbers, emails) — delegates to golden.security."""
    return redact_text(message)


# ── Enrichment ────────────────────────────────────────────────────────────────
def enrich(record: LogRecord) -> LogRecord:
    """Add platform-level labels to the record."""
    record.extra.setdefault("platform", PLATFORM_LABEL)
    record.extra.setdefault("environment", ENVIRONMENT)
    return record


# ── Routing ───────────────────────────────────────────────────────────────────
def route_log(record: dict) -> dict:
    """
    Main entry point for external callers.

    Accepts a raw log dict, parses, enriches, optionally redacts PHI,
    and returns the routed record with Loki stream labels attached.
    """
    log = LogRecord.from_dict(record)
    log = enrich(log)

    if log.vertical == Vertical.HEALTHCARE:
        log.message = redact_phi(log.message)

    loki_labels = _build_loki_labels(log)
    return {
        "status": "routed",
        "vertical": log.vertical.value,
        "loki_labels": loki_labels,
        "record": _to_loki_entry(log),
    }


def _build_loki_labels(log: LogRecord) -> dict[str, str]:
    return {
        "job": log.service,
        "vertical": log.vertical.value,
        "level": log.level,
        "platform": PLATFORM_LABEL,
        "environment": ENVIRONMENT,
    }


def _to_loki_entry(log: LogRecord) -> dict:
    line = json.dumps(
        {
            "message": log.message,
            "service": log.service,
            "level": log.level,
            "traceID": log.trace_id,
            "spanID": log.span_id,
            **log.extra,
        },
        default=str,
    )
    return {"ts": str(log.timestamp_ns), "line": line}


# ── Loki Shipper ─────────────────────────────────────────────────────────────
class LokiShipper:
    """
    Batches log entries and ships them to Loki via the HTTP push API.
    Thread-safe batching with a configurable flush interval.
    """

    def __init__(
        self,
        push_url: str = LOKI_PUSH_URL,
        batch_size: int = 100,
        flush_interval: float = 1.0,
    ) -> None:
        if not push_url.startswith(("http://", "https://")):
            raise ValueError("Loki push URL must be http(s)")
        self.push_url = push_url
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._batch: list[tuple[dict, LogRecord]] = []
        self._last_flush = time.monotonic()

    def push(self, record: dict) -> None:
        """Route and buffer a raw log dict; flush when threshold is reached."""
        routed = route_log(record)
        log = LogRecord.from_dict(record)
        self._batch.append((routed["loki_labels"], log))
        if len(self._batch) >= self.batch_size or self._should_flush():
            self.flush()

    def flush(self) -> None:
        """Ship all buffered entries to Loki in grouped streams."""
        if not self._batch:
            return
        payload = self._build_payload(self._batch)
        self._batch = []
        self._last_flush = time.monotonic()
        self._send(payload)

    def _should_flush(self) -> bool:
        return (time.monotonic() - self._last_flush) >= self.flush_interval

    def _build_payload(self, batch: list[tuple[dict, LogRecord]]) -> dict:
        streams: dict[str, dict[str, Any]] = {}
        for labels, log in batch:
            key = json.dumps(labels, sort_keys=True)
            entry = [str(log.timestamp_ns), _to_loki_entry(log)["line"]]
            streams.setdefault(key, {"stream": labels, "values": []})["values"].append(entry)
        return {"streams": list(streams.values())}

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(  # noqa: S310 - scheme validated in __init__
            self.push_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
                if resp.status not in (200, 204):
                    logger.warning("Loki push returned HTTP %s", resp.status)
        except urllib.error.URLError as exc:
            logger.error("Failed to push logs to Loki: %s", exc)
