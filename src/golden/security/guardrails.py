"""Input guardrails and output caps for every model the platform serves.

Models only ever see inputs that are finite, bounded in size and inside physically plausible ranges;
scores leaving the platform are always clamped to ``[0, 1]``. Inputs that are valid but far outside
the training distribution are flagged so downstream automation can refuse to act on them.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

MAX_SEQUENCE_LENGTH = 4096
MAX_BATCH_SIZE = 10_000


class GuardrailViolation(ValueError):
    """Raised when an input fails a guardrail. ``reason`` is a stable, metric-friendly slug."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def ensure_finite(value: float, name: str = "value") -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GuardrailViolation("non_numeric", f"{name} is not a number") from exc
    if not math.isfinite(number):
        raise GuardrailViolation("non_finite", f"{name} must be finite")
    return number


def ensure_in_range(value: float, low: float, high: float, name: str = "value") -> float:
    number = ensure_finite(value, name)
    if number < low or number > high:
        raise GuardrailViolation("out_of_range", f"{name}={number} outside [{low}, {high}]")
    return number


def validate_sequence(
    values: Iterable[float],
    *,
    min_length: int = 1,
    max_length: int = MAX_SEQUENCE_LENGTH,
    low: float = -1e9,
    high: float = 1e9,
    name: str = "sequence",
) -> list[float]:
    """Return ``values`` as a list of floats or raise :class:`GuardrailViolation`."""
    out: list[float] = []
    for i, raw in enumerate(values):
        if i >= max_length:
            raise GuardrailViolation("sequence_too_long", f"{name} exceeds {max_length} points")
        out.append(ensure_in_range(raw, low, high, f"{name}[{i}]"))
    if len(out) < min_length:
        raise GuardrailViolation("sequence_too_short", f"{name} needs at least {min_length} points")
    return out


def validate_batch_size(n: int, max_size: int = MAX_BATCH_SIZE) -> int:
    if n > max_size:
        raise GuardrailViolation("batch_too_large", f"{n} items exceeds cap of {max_size}")
    return n


def clamp_score(score: float) -> float:
    """Cap a model score to ``[0, 1]``; NaN/inf collapse to 0 so a broken model can't trigger actions."""
    try:
        number = float(score)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return min(1.0, max(0.0, number))


@dataclass(frozen=True)
class FeatureBound:
    low: float
    high: float


def check_bounds(features: Mapping[str, float], bounds: Mapping[str, FeatureBound]) -> dict[str, float]:
    """Validate each bounded feature present in ``features``; unknown keys pass through untouched."""
    checked = dict(features)
    for key, bound in bounds.items():
        if key in features and features[key] is not None:
            checked[key] = ensure_in_range(features[key], bound.low, bound.high, key)
    return checked


@dataclass(frozen=True)
class OODResult:
    is_out_of_distribution: bool
    max_abs_z: float
    feature: str | None


class OODDetector:
    """Flags inputs whose z-score vs. reference statistics exceeds ``threshold``.

    Cheap, explainable and dependency-free: the right first line of defence against adversarial or
    corrupted telemetry before it reaches a learned model.
    """

    def __init__(self, reference: Mapping[str, tuple[float, float]], threshold: float = 6.0) -> None:
        self.reference = dict(reference)  # feature -> (mean, std)
        self.threshold = threshold

    @classmethod
    def fit(cls, rows: Sequence[Mapping[str, float]], threshold: float = 6.0) -> OODDetector:
        if not rows:
            raise ValueError("cannot fit OODDetector on an empty sample")
        stats: dict[str, tuple[float, float]] = {}
        for key in rows[0]:
            column = [float(r[key]) for r in rows if key in r]
            mean = sum(column) / len(column)
            var = sum((v - mean) ** 2 for v in column) / max(len(column) - 1, 1)
            stats[key] = (mean, math.sqrt(var))
        return cls(stats, threshold)

    def check(self, features: Mapping[str, float]) -> OODResult:
        worst, worst_key = 0.0, None
        for key, (mean, std) in self.reference.items():
            if key not in features:
                continue
            z = abs(float(features[key]) - mean) / (std if std > 1e-12 else 1.0)
            if z > worst:
                worst, worst_key = z, key
        return OODResult(worst > self.threshold, round(worst, 3), worst_key)


# Physically plausible ranges shared by the services' request validation.
VITALS_BOUNDS = {
    "heart_rate": FeatureBound(20, 300),
    "spo2": FeatureBound(40, 100),
    "systolic_bp": FeatureBound(40, 300),
    "diastolic_bp": FeatureBound(20, 200),
    "temperature": FeatureBound(25, 45),
    "respiratory_rate": FeatureBound(0, 80),
}
TRANSACTION_BOUNDS = {"amount": FeatureBound(0, 10_000_000)}
GPU_BOUNDS = {
    "utilization_pct": FeatureBound(0, 100),
    "memory_used_pct": FeatureBound(0, 100),
    "temperature_c": FeatureBound(0, 130),
    "power_w": FeatureBound(0, 2000),
}
