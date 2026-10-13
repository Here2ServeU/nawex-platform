"""Checkpointed runs and drain-on-rollout.

Every completed step is written atomically (tmp + rename), so a crash, a budget drain or a Kubernetes
rollout (SIGTERM → ``terminationGracePeriodSeconds``) loses at most the step in flight. A resumed run
skips completed steps — the money already spent is not spent again.
"""

from __future__ import annotations

import json
import signal
import threading
from pathlib import Path
from typing import Any


class CheckpointStore:
    def __init__(self, state_dir: str | Path = ".agentops", enabled: bool = True) -> None:
        self.dir = Path(state_dir) / "checkpoints"
        self.enabled = enabled

    def _path(self, task_id: str) -> Path:
        return self.dir / f"{task_id}.json"

    def load(self, task_id: str) -> dict[str, Any]:
        p = self._path(task_id)
        if not self.enabled or not p.exists():
            return {"completed": [], "spent_usd": 0.0}
        return json.loads(p.read_text())

    def save(self, task_id: str, state: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._path(task_id).with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        tmp.replace(self._path(task_id))

    def clear(self, task_id: str) -> None:
        self._path(task_id).unlink(missing_ok=True)


class DrainSignal:
    """Set on SIGTERM/SIGINT; the runner finishes the current step, checkpoints and exits ``drained``."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def request(self, *_: Any) -> None:
        self._event.set()

    def install(self) -> None:
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self.request)
