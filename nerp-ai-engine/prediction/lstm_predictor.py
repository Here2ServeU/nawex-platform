"""Inference wrapper for LSTM SLI predictor."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def predict_lstm(features: Sequence[float], model_path: str | Path | None = None) -> float:
    """Predict risk score from a numeric sequence.

    If no model checkpoint exists, this returns a conservative statistical proxy.
    """
    values = [float(x) for x in features]
    if len(values) < 3:
        return 0.0

    checkpoint = Path(model_path) if model_path else Path(__file__).resolve().parents[1] / "models" / "lstm_model.pt"
    model = None
    try:
        from ..models.lstm_model import LSTMSLIPredictor

        model = LSTMSLIPredictor.load(str(checkpoint), input_size=1)
    except ModuleNotFoundError:
        model = None

    if model is None:
        # Fallback proxy: larger recent spike => higher risk.
        baseline = sum(values[:-1]) / max(1, len(values) - 1)
        latest = values[-1]
        delta_ratio = (latest - baseline) / (abs(baseline) + 1e-6)
        return float(max(0.0, min(1.0, delta_ratio)))

    return float(model.predict_risk(values))
