"""Tamper-evident audit log: every entry carries the SHA-256 of its predecessor.

Editing or deleting any entry breaks the chain, which :meth:`AuditLog.verify` detects. Entries are
redacted before they are hashed so PHI/PII never lands in the trail.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from golden.security.redaction import redact_obj

GENESIS = "0" * 64


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    ts: str
    actor: str
    event: str
    data: dict[str, Any]
    prev_hash: str
    hash: str


def _digest(seq: int, ts: str, actor: str, event: str, data: dict[str, Any], prev_hash: str) -> str:
    body = json.dumps(
        {"seq": seq, "ts": ts, "actor": actor, "event": event, "data": data, "prev": prev_hash},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(body.encode()).hexdigest()


class AuditLog:
    def __init__(self, path: str | Path | None = None) -> None:
        self._entries: list[AuditEntry] = []
        self._lock = threading.Lock()
        self._path = Path(path) if path else None
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event: str, data: dict[str, Any] | None = None, actor: str = "system") -> AuditEntry:
        with self._lock:
            seq = len(self._entries)
            prev = self._entries[-1].hash if self._entries else GENESIS
            ts = datetime.now(UTC).isoformat()
            clean = redact_obj(data or {})
            entry = AuditEntry(
                seq, ts, actor, event, clean, prev, _digest(seq, ts, actor, event, clean, prev)
            )
            self._entries.append(entry)
            if self._path:
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(entry), default=str) + "\n")
            return entry

    def entries(self) -> list[AuditEntry]:
        with self._lock:
            return list(self._entries)

    @staticmethod
    def verify_entries(entries: list[AuditEntry]) -> bool:
        prev = GENESIS
        for i, e in enumerate(entries):
            if e.seq != i or e.prev_hash != prev:
                return False
            if _digest(e.seq, e.ts, e.actor, e.event, e.data, e.prev_hash) != e.hash:
                return False
            prev = e.hash
        return True

    def verify(self) -> bool:
        return self.verify_entries(self.entries())


_default: AuditLog | None = None


def default_audit_log() -> AuditLog:
    """Process-wide audit log (file-backed when ``GOLDEN_AUDIT_LOG`` is set)."""
    global _default
    if _default is None:
        from golden.config import get_settings

        _default = AuditLog(get_settings().audit_log_path or None)
    return _default
