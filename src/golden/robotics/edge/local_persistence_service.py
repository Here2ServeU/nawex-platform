"""Edge buffering: persist telemetry locally during cloud disconnects for later sync."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


class LocalPersistenceService:
    def __init__(self, storage_path: str | Path | None = None, max_files: int = 100_000) -> None:
        self.storage_path = Path(
            storage_path
            or os.getenv("GOLDEN_EDGE_BUFFER")
            or Path(tempfile.gettempdir()) / "golden-edge-buffer"
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.max_files = max_files

    def save_telemetry_locally(self, telemetry: dict[str, Any]) -> Path | None:
        if sum(1 for _ in self.storage_path.glob("telemetry_*.json")) >= self.max_files:
            return None  # bounded disk use; caller should shed load
        path = self.storage_path / f"telemetry_{time.time_ns()}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(telemetry), encoding="utf-8")
        tmp.replace(path)  # atomic publish
        return path

    def drain(self) -> list[dict[str, Any]]:
        """Read and remove buffered packets in arrival order (called when the uplink returns)."""
        items = []
        for path in sorted(self.storage_path.glob("telemetry_*.json")):
            items.append(json.loads(path.read_text(encoding="utf-8")))
            path.unlink()
        return items
