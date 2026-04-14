"""Inference wrapper for TCN SLI predictor."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def predict_tcn(features: Sequence[float], model_path: str | Path | None = None) -> float:
    """Predict risk score from a numeric sequence.

    If no checkpoint is available, use a trend-amplified fallback score.
    """
    values = [float(x) for x in features]
    if len(values) < 4:
        return 0.0

    checkpoint = Path(model_path) if model_path else Path(__file__).resolve().parents[1] / "models" / "tcn_model.pt"
    model = None
    try:
        from ..models.tcn_model import TCNSLIPredictor

        model = TCNSLIPredictor.load(str(checkpoint), input_size=1)
    except ModuleNotFoundError:
        model = None

    if model is None:
        tail = values[-4:]
        slope = (tail[-1] - tail[0]) / 3.0
        mean = sum(abs(v) for v in tail) / 4.0
        risk = slope / (mean + 1e-6)
        return float(max(0.0, min(1.0, risk)))

    return float(model.predict_risk(values))
