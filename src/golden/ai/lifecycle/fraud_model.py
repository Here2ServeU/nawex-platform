"""Trained fraud classifier — logistic regression in numpy, serialised as JSON (never pickle).

Features (no label leakage — the simulator's ``fraud_score`` is excluded): log amount, channel one-hot,
high-risk country. (Hour of day is deliberately absent: the simulator stamps transactions relative to
``now()``, so the hour carries no stable signal and made training results depend on the wall clock.) Class-weighted gradient descent handles the ~4% fraud rate.
JSON weights mean a model file can be reviewed, diffed and loaded without executing code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CHANNELS = ("pos", "online", "mobile", "card_not_present", "atm")
HIGH_RISK_COUNTRIES = frozenset({"NG", "RU", "KP", "IR", "VE"})
FEATURES = ("log_amount", *(f"ch_{c}" for c in CHANNELS), "high_risk_country")


def featurize(df: pd.DataFrame) -> np.ndarray:
    cols = [np.log1p(df["amount"].to_numpy(dtype=float))]
    cols += [(df["channel"] == c).to_numpy(dtype=float) for c in CHANNELS]
    cols.append(df["country_code"].isin(HIGH_RISK_COUNTRIES).to_numpy(dtype=float))
    return np.column_stack(cols)


def auc(y: np.ndarray, scores: np.ndarray) -> float:
    """Rank-based ROC AUC (Mann–Whitney U)."""
    pos, neg = scores[y == 1], scores[y == 0]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    ranks = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((ranks[: pos.size].sum() - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size))


@dataclass
class FraudModel:
    weights: np.ndarray
    bias: float
    mean: np.ndarray
    std: np.ndarray
    threshold: float = 0.5

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        z = ((x - self.mean) / self.std) @ self.weights + self.bias
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))

    def predict(self, x: np.ndarray) -> np.ndarray:
        return (self.predict_proba(x) >= self.threshold).astype(int)

    def evaluate(self, x: np.ndarray, y: np.ndarray) -> dict[str, float]:
        p = self.predict(x)
        tp = int(((p == 1) & (y == 1)).sum())
        fp = int(((p == 1) & (y == 0)).sum())
        fn = int(((p == 0) & (y == 1)).sum())
        tn = int(((p == 0) & (y == 0)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
            "auc": round(auc(y, self.predict_proba(x)), 4),
            "fp_rate": round(fp / (fp + tn), 5) if fp + tn else 0.0,
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "type": "logistic_regression",
                    "features": FEATURES,
                    "weights": self.weights.tolist(),
                    "bias": self.bias,
                    "mean": self.mean.tolist(),
                    "std": self.std.tolist(),
                    "threshold": self.threshold,
                },
                indent=2,
            )
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> FraudModel:
        d: dict[str, Any] = json.loads(Path(path).read_text())
        if tuple(d["features"]) != FEATURES:
            raise ValueError("model feature set does not match this code version")
        return cls(
            np.array(d["weights"]),
            float(d["bias"]),
            np.array(d["mean"]),
            np.array(d["std"]),
            float(d["threshold"]),
        )


def train(
    df: pd.DataFrame, *, epochs: int = 600, lr: float = 0.2, l2: float = 1e-3, seed: int = 0
) -> tuple[FraudModel, dict[str, float]]:
    """Stratified 80/20 split, class-weighted logistic regression; returns the model and holdout metrics."""
    rng = np.random.default_rng(seed)
    x, y = featurize(df), df["is_fraud"].to_numpy(dtype=int)
    test = np.zeros(len(y), dtype=bool)
    for label in (0, 1):
        idx = np.flatnonzero(y == label)
        test[rng.choice(idx, size=max(1, len(idx) // 5), replace=False)] = True
    xtr, ytr = x[~test], y[~test]
    mean, std = xtr.mean(0), xtr.std(0) + 1e-9
    xs = (xtr - mean) / std
    pos_w = (ytr == 0).sum() / max(1, (ytr == 1).sum())
    sample_w = np.where(ytr == 1, pos_w, 1.0)
    w, b = np.zeros(x.shape[1]), 0.0
    for _ in range(epochs):
        p = 1 / (1 + np.exp(-np.clip(xs @ w + b, -30, 30)))
        g = sample_w * (p - ytr) / sample_w.sum()
        w -= lr * (xs.T @ g + l2 * w)
        b -= lr * g.sum()
    model = FraudModel(w, float(b), mean, std)
    # Calibrate the decision threshold on training data with F2 (recall weighted 2x precision): for fraud
    # a missed fraud costs more than a false alarm, and class weighting alone over-flags.
    probs = model.predict_proba(xtr)
    positives = float((ytr == 1).sum())
    best = -1.0
    for t in np.linspace(0.05, 0.95, 91):
        pred = probs >= t
        tp = float((pred & (ytr == 1)).sum())
        precision = tp / pred.sum() if pred.sum() else 0.0
        recall = tp / positives if positives else 0.0
        f2 = 5 * precision * recall / (4 * precision + recall) if precision + recall else 0.0
        if f2 > best:
            best, model.threshold = f2, float(t)
    return model, model.evaluate(x[test], y[test])
