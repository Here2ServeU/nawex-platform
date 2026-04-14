"""Evaluation metrics for model and detector quality checks."""

from __future__ import annotations

import math
from typing import Sequence, Dict


def regression_metrics(y_true: Sequence[float], y_pred: Sequence[float]) -> Dict[str, float]:
    """Compute common regression metrics without external dependencies."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same shape")

    yt = [float(v) for v in y_true]
    yp = [float(v) for v in y_pred]
    n = len(yt)
    if n == 0:
        raise ValueError("Empty inputs are not supported")

    errors = [a - b for a, b in zip(yt, yp)]
    mse = sum(e * e for e in errors) / n
    rmse = math.sqrt(mse)
    mae = sum(abs(e) for e in errors) / n

    mean_true = sum(yt) / n
    variance = sum((v - mean_true) ** 2 for v in yt)
    residual = sum(e * e for e in errors)
    r2 = 1.0 - (residual / variance) if variance > 0 else 0.0

    return {
        "mse": float(mse),
        "rmse": float(rmse),
        "mae": float(mae),
        "r2": float(r2),
    }


def classification_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> Dict[str, float]:
    """Compute binary classification metrics for anomaly/fraud tasks."""
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same shape")

    yt = [int(v) for v in y_true]
    yp = [int(v) for v in y_pred]

    tp = sum(1 for a, b in zip(yt, yp) if a == 1 and b == 1)
    tn = sum(1 for a, b in zip(yt, yp) if a == 0 and b == 0)
    fp = sum(1 for a, b in zip(yt, yp) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(yt, yp) if a == 1 and b == 0)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = (2 * precision * recall) / max(precision + recall, 1e-9)
    accuracy = (tp + tn) / max(tp + tn + fp + fn, 1)

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tp": float(tp),
        "tn": float(tn),
        "fp": float(fp),
        "fn": float(fn),
    }
