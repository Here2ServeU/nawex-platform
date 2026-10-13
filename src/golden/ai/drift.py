"""Distribution drift: Population Stability Index (PSI) and the two-sample Kolmogorov–Smirnov test.

Used for model inputs/scores (retraining trigger, promotion gate) and for agent behaviour (steps,
cost, tool mix, output length vs a baseline). Pure numpy — no scipy dependency.

PSI bands (industry convention): < 0.1 stable · 0.1–0.25 moderate shift · > 0.25 significant shift.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import numpy as np
import numpy.typing as npt

PSI_MODERATE = 0.1
PSI_SIGNIFICANT = 0.25


def psi(expected: npt.ArrayLike, actual: npt.ArrayLike, bins: int = 10, eps: float = 1e-6) -> float:
    """PSI with quantile bins from ``expected`` (the baseline)."""
    e = np.asarray(expected, dtype=float)
    a = np.asarray(actual, dtype=float)
    if e.size == 0 or a.size == 0:
        raise ValueError("psi needs non-empty samples")
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if edges.size < 3:  # (near-)constant baseline: one bin for the baseline value, one either side
        lo, hi = float(e.min()), float(e.max())
        edges = np.array([-np.inf, lo, np.nextafter(hi, np.inf), np.inf])
    else:
        edges[0], edges[-1] = -np.inf, np.inf
    pe = np.histogram(e, edges)[0] / e.size + eps
    pa = np.histogram(a, edges)[0] / a.size + eps
    return float(np.sum((pa - pe) * np.log(pa / pe)))


def psi_categorical(expected: Sequence[str], actual: Sequence[str], eps: float = 1e-6) -> float:
    cats = sorted(set(expected) | set(actual))
    pe = np.array([list(expected).count(c) / max(1, len(expected)) for c in cats]) + eps
    pa = np.array([list(actual).count(c) / max(1, len(actual)) for c in cats]) + eps
    return float(np.sum((pa - pe) * np.log(pa / pe)))


def ks_2samp(x: npt.ArrayLike, y: npt.ArrayLike) -> tuple[float, float]:
    """Two-sample KS statistic and asymptotic p-value (Smirnov), matching scipy's 'asymp' method."""
    a, b = np.sort(np.asarray(x, dtype=float)), np.sort(np.asarray(y, dtype=float))
    n, m = a.size, b.size
    if n == 0 or m == 0:
        raise ValueError("ks_2samp needs non-empty samples")
    grid = np.concatenate([a, b])
    cdf_a = np.searchsorted(a, grid, side="right") / n
    cdf_b = np.searchsorted(b, grid, side="right") / m
    d = float(np.max(np.abs(cdf_a - cdf_b)))
    en = math.sqrt(n * m / (n + m))
    lam = (en + 0.12 + 0.11 / en) * d
    p = 2 * sum((-1) ** (k - 1) * math.exp(-2 * (k * lam) ** 2) for k in range(1, 101))
    return d, float(min(1.0, max(0.0, p)))


@dataclass
class DriftReport:
    feature: str
    psi: float
    ks_statistic: float
    p_value: float
    drifted: bool
    band: str

    def to_dict(self) -> dict:
        return asdict(self)


def detect_drift(
    feature: str, baseline: npt.ArrayLike, current: npt.ArrayLike, *, alpha: float = 0.05
) -> DriftReport:
    value = psi(baseline, current)
    d, p = ks_2samp(baseline, current)
    band = "significant" if value > PSI_SIGNIFICANT else ("moderate" if value > PSI_MODERATE else "stable")
    return DriftReport(
        feature, round(value, 4), round(d, 4), round(p, 6), value > PSI_SIGNIFICANT or p < alpha, band
    )
