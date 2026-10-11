"""LSTM breach-risk prediction with a statistical fallback when no trained model is available."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from golden.ai.prediction._loader import load_cached
from golden.security.guardrails import clamp_score, validate_sequence


def predict_lstm(features: Sequence[float], model_path: str | Path | None = None) -> float:
    """Return a ``[0, 1]`` SLO-breach risk for a latency sequence."""
    values = validate_sequence(features, min_length=0, low=-1e7, high=1e7)
    if len(values) < 3:
        return 0.0
    model = load_cached("lstm", model_path)
    if model is not None:
        return clamp_score(model.predict_risk(values))
    # Fallback proxy: relative jump of the latest point over the running baseline.
    baseline = sum(values[:-1]) / (len(values) - 1)
    return clamp_score((values[-1] - baseline) / (abs(baseline) + 1e-6))
