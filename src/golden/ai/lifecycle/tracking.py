"""Experiment tracking: every training run records params, metrics, tags and its artifact.

File-backed (``<root>/runs.jsonl``) so it works offline and in CI. When ``MLFLOW_TRACKING_URI`` is set
and ``mlflow`` is installed, runs are mirrored to MLflow as well (same params/metrics/tags), so teams
already on MLflow keep their UI.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TrackedRun:
    run_id: str
    experiment: str
    params: dict[str, Any]
    metrics: dict[str, float]
    tags: dict[str, str] = field(default_factory=dict)
    artifact: str = ""
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExperimentTracker:
    def __init__(self, root: str | Path = "models/registry") -> None:
        self.root = Path(root)
        self.path = self.root / "runs.jsonl"

    def log_run(
        self,
        experiment: str,
        params: dict[str, Any],
        metrics: dict[str, float],
        *,
        tags: dict[str, str] | None = None,
        artifact: str = "",
    ) -> TrackedRun:
        run = TrackedRun(uuid.uuid4().hex[:12], experiment, params, metrics, tags or {}, artifact)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(run.to_dict()) + "\n")
        self._mirror_mlflow(run)
        return run

    def runs(self, experiment: str | None = None) -> list[TrackedRun]:
        if not self.path.exists():
            return []
        rows = [TrackedRun(**json.loads(line)) for line in self.path.read_text().splitlines() if line.strip()]
        return [r for r in rows if experiment is None or r.experiment == experiment]

    def best(self, experiment: str, metric: str) -> TrackedRun | None:
        runs = [r for r in self.runs(experiment) if metric in r.metrics]
        return max(runs, key=lambda r: r.metrics[metric], default=None)

    @staticmethod
    def _mirror_mlflow(run: TrackedRun) -> None:
        if not os.getenv("MLFLOW_TRACKING_URI"):
            return
        try:  # pragma: no cover - optional integration
            import mlflow

            mlflow.set_experiment(run.experiment)
            with mlflow.start_run(run_name=run.run_id):
                mlflow.log_params(run.params)
                mlflow.log_metrics(run.metrics)
                mlflow.set_tags(run.tags)
                if run.artifact:
                    mlflow.log_artifact(run.artifact)
        except Exception:  # tracking must never fail training
            logger.warning("mlflow mirror failed", exc_info=True)
