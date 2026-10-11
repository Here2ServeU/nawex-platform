"""TCN breach-risk prediction with a trend-based fallback when no trained model is available."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from golden.ai.prediction._loader import load_cached
from golden.security.guardrails import clamp_score, validate_sequence


def predict_tcn(features: Sequence[float], model_path: str | Path | None = None) -> float:
    """Return a ``[0, 1]`` SLO-breach risk for a latency sequence."""
    values = validate_sequence(features, min_length=0, low=-1e7, high=1e7)
    if len(values) < 4:
        return 0.0
    model = load_cached("tcn", model_path)
    if model is not None:
        return clamp_score(model.predict_risk(values))
    tail = values[-4:]
    slope = (tail[-1] - tail[0]) / 3.0
    mean = sum(abs(v) for v in tail) / 4.0
    return clamp_score(slope / (mean + 1e-6))
