"""Runtime model loading and inference helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

from ..prediction.lstm_predictor import predict_lstm
from ..prediction.tcn_predictor import predict_tcn


def run_all_predictors(sequence: Sequence[float], model_dir: str | Path = "models") -> Dict[str, float]:
    """Run LSTM and TCN predictors and return side-by-side scores."""
    model_dir = Path(model_dir)
    return {
        "lstm_score": predict_lstm(sequence, model_path=model_dir / "lstm_model.pt"),
        "tcn_score": predict_tcn(sequence, model_path=model_dir / "tcn_model.pt"),
    }


def aggregate_risk(scores: Dict[str, float], weights: Dict[str, float] | None = None) -> float:
    """Combine multiple predictor scores into a single risk signal."""
    if not scores:
        return 0.0

    if weights is None:
        weights = {k: 1.0 for k in scores}

    numerator = 0.0
    denominator = 0.0
    for name, score in scores.items():
        w = float(weights.get(name, 1.0))
        numerator += float(score) * w
        denominator += w

    return numerator / max(denominator, 1e-9)
