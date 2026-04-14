"""Isolation Forest anomaly detector wrapper."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np


def _validate_2d_array(data: Any) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2:
        raise ValueError("Expected a 2D array-like input with shape (n_samples, n_features).")
    if arr.shape[0] < 16:
        raise ValueError("Need at least 16 samples to train isolation forest.")
    return arr


def train_isolation_forest(data: Any, contamination: float = 0.03, random_state: int = 42) -> Dict[str, Any]:
    """Fit an IsolationForest and return a small artifact dictionary."""
    x = _validate_2d_array(data)

    try:
        from sklearn.ensemble import IsolationForest
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "scikit-learn is required for train_isolation_forest. Install with 'pip install scikit-learn'."
        ) from exc

    model = IsolationForest(
        n_estimators=200,
        contamination=float(np.clip(contamination, 0.001, 0.5)),
        random_state=random_state,
    )
    model.fit(x)
    scores = -model.score_samples(x)

    return {
        "kind": "isolation_forest",
        "model": model,
        "mean_score": float(scores.mean()),
        "std_score": float(scores.std()),
    }


def score_isolation_forest(data: Any, artifact: Dict[str, Any]) -> np.ndarray:
    """Return anomaly scores (higher means more anomalous)."""
    x = _validate_2d_array(data)
    model = artifact["model"]
    return -model.score_samples(x)
