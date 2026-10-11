"""End-to-end AI engine demo: train (GPU-aware) → integrity-checked inference → explain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from golden.ai.datasets import make_sli_dataset
from golden.ai.evaluation import regression_metrics
from golden.ai.explainability import build_text_report
from golden.ai.inference import aggregate_risk, run_all_predictors


def run_demo(epochs: int = 1, output_dir: Path = Path(".artifacts/demo")) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, str] = {}
    training: dict[str, Any] = {"mode": "fallback"}
    try:
        from golden.ai.training import train_and_save

        for kind in ("lstm", "tcn"):
            trained = train_and_save(kind, output_dir=output_dir, epochs=max(epochs, 1))
            artifacts[kind] = trained.path
            training = {"mode": "trained", "device": trained.device}
    except ImportError as exc:  # [ml] extra not installed
        training["reason"] = str(exc)

    sequence = [float(v) for v in make_sli_dataset(n_rows=60)["latency_ms"].tail(24)]
    scores = run_all_predictors(sequence, model_dir=output_dir if artifacts else None)
    risk = aggregate_risk(scores)
    baseline = sequence[-1]
    quality = regression_metrics([baseline + d for d in (8.0, 10.0, 12.0)], [baseline + 12.0 * risk] * 3)
    report = build_text_report(
        {
            "latency_recent_trend": scores["tcn_score"],
            "latency_level_shift": scores["lstm_score"],
            "error_budget_pressure": max(0.0, risk - 0.15),
        },
        top_k=3,
    )
    result = {
        "artifacts": artifacts,
        "training": training,
        "risk_scores": scores,
        "aggregate_risk": round(risk, 4),
        "evaluation": quality,
        "explainability": report,
    }
    (output_dir / "demo_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
