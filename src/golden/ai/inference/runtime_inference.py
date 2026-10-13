"""Runtime inference: run every predictor and blend the scores into one risk signal."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from golden.ai.prediction.lstm_predictor import predict_lstm
from golden.ai.prediction.tcn_predictor import predict_tcn
from golden.security.guardrails import clamp_score


def run_all_predictors(sequence: Sequence[float], model_dir: str | Path | None = None) -> dict[str, float]:
    """Run LSTM and TCN predictors side by side."""
    lstm_path = Path(model_dir) / "lstm_model.pt" if model_dir else None
    tcn_path = Path(model_dir) / "tcn_model.pt" if model_dir else None
    return {
        "lstm_score": predict_lstm(sequence, model_path=lstm_path),
        "tcn_score": predict_tcn(sequence, model_path=tcn_path),
    }


def aggregate_risk(scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Weighted mean of predictor scores, capped to ``[0, 1]``."""
    if not scores:
        return 0.0
    weights = weights or {k: 1.0 for k in scores}
    numerator = sum(clamp_score(s) * float(weights.get(k, 1.0)) for k, s in scores.items())
    denominator = sum(float(weights.get(k, 1.0)) for k in scores)
    return clamp_score(numerator / max(denominator, 1e-9))
