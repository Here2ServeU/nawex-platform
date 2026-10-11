"""Lightweight autoencoder-style anomaly detector for tabular telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class AutoencoderArtifact:
    """Serializable artifact returned after fitting the detector."""

    center: np.ndarray
    threshold: float
    reconstruction_errors: np.ndarray


def _validate_2d_array(data: Any) -> np.ndarray:
    arr = np.asarray(data, dtype=float)
    if arr.ndim != 2:
        raise ValueError("Expected a 2D array-like input with shape (n_samples, n_features).")
    if arr.shape[0] < 10:
        raise ValueError("Need at least 10 samples to train anomaly detector.")
    return arr


def train_autoencoder(data: Any, contamination: float = 0.05) -> dict[str, Any]:
    """Train a simple reconstruction-error detector.

    This implementation uses feature-centroid reconstruction as a deterministic,
    dependency-light baseline that can run in constrained demo environments.
    """
    x = _validate_2d_array(data)
    contamination = float(np.clip(contamination, 0.001, 0.5))

    center = x.mean(axis=0)
    reconstruction_errors = np.sqrt(((x - center) ** 2).mean(axis=1))
    threshold = float(np.quantile(reconstruction_errors, 1 - contamination))

    artifact = AutoencoderArtifact(
        center=center,
        threshold=threshold,
        reconstruction_errors=reconstruction_errors,
    )
    return {
        "kind": "centroid_autoencoder",
        "threshold": artifact.threshold,
        "feature_dim": int(center.shape[0]),
        "artifact": artifact,
    }


def score_autoencoder(data: Any, artifact: dict[str, Any]) -> np.ndarray:
    """Compute anomaly scores using a trained artifact."""
    x = _validate_2d_array(data)
    model = artifact["artifact"]
    center = model.center
    return np.sqrt(((x - center) ** 2).mean(axis=1))
