"""Drift-triggered retraining with a quality gate.

1. compare the current window to the training baseline (PSI + KS on amount and model score);
2. no drift and not forced → stop;
3. retrain, log the run, and register the result as ``challenger`` only if it passes the gate
   (default recall ≥ 0.70, AUC ≥ 0.90, FP rate ≤ 5%). Promotion to champion stays a separate,
   human-approved step (:meth:`ModelRegistry.promote`).
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from golden.ai.drift import detect_drift
from golden.ai.lifecycle.fraud_model import FraudModel, featurize, train
from golden.ai.lifecycle.registry import ModelRegistry
from golden.ai.lifecycle.tracking import ExperimentTracker

MODEL_NAME = "fraud-detector"
DEFAULT_GATES = {"recall": 0.70, "auc": 0.90, "fp_rate": 0.05}


def check_drift(
    baseline: pd.DataFrame, current: pd.DataFrame, model: FraudModel | None = None
) -> dict[str, Any]:
    reports = [detect_drift("amount", baseline["amount"], current["amount"])]
    if model is not None:
        reports.append(
            detect_drift(
                "score", model.predict_proba(featurize(baseline)), model.predict_proba(featurize(current))
            )
        )
    return {"drifted": any(r.drifted for r in reports), "features": [r.to_dict() for r in reports]}


def _passes(metrics: dict[str, float], gates: dict[str, float]) -> list[str]:
    fails = []
    for k, v in gates.items():
        ok = metrics.get(k, 0) <= v if k == "fp_rate" else metrics.get(k, 0) >= v
        if not ok:
            fails.append(f"{k}={metrics.get(k)} (gate {v})")
    return fails


def retrain_if_drifted(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
    *,
    root: str | Path = "models/registry",
    gates: dict[str, float] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    registry, tracker = ModelRegistry(root), ExperimentTracker(root)
    gates = gates or DEFAULT_GATES
    champion = None
    with contextlib.suppress(KeyError):
        champion = FraudModel.load(registry.get(MODEL_NAME, "champion").artifact)
    drift = check_drift(baseline, current, champion)
    if not drift["drifted"] and not force and champion is not None:
        return {"action": "none", "drift": drift}
    model, metrics = train(pd.concat([baseline, current], ignore_index=True))
    with tempfile.TemporaryDirectory() as tmp:
        artifact = model.save(Path(tmp) / "model.json")
        run = tracker.log_run(
            "fraud-auto-retrain",
            {"epochs": 600, "rows": len(baseline) + len(current)},
            metrics,
            tags={
                "trigger": "drift" if drift["drifted"] else ("bootstrap" if champion is None else "forced")
            },
            artifact=str(artifact),
        )
        failures = _passes(metrics, gates)
        if failures:
            return {
                "action": "rejected",
                "drift": drift,
                "metrics": metrics,
                "failures": failures,
                "run_id": run.run_id,
            }
        alias = "champion" if champion is None else "challenger"  # first model bootstraps the champion slot
        mv = registry.register(MODEL_NAME, artifact, metrics, run_id=run.run_id, alias=alias)
    return {
        "action": "registered",
        "alias": alias,
        "version": mv.version,
        "drift": drift,
        "metrics": metrics,
        "run_id": run.run_id,
    }
