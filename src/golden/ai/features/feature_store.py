"""Feature assembly helpers used by training and inference pipelines."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def required_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    """Raise a clear error if required columns are missing."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def build_reliability_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Create model-ready reliability features from raw telemetry."""
    required_columns(df, ["latency_ms", "error_rate_percent", "cpu_usage_percent"])

    out = df.copy()
    out["latency_x_error"] = out["latency_ms"] * out["error_rate_percent"]
    out["cpu_pressure"] = out["cpu_usage_percent"] / 100.0
    out["latency_delta"] = out["latency_ms"].diff().fillna(0.0)
    out["error_delta"] = out["error_rate_percent"].diff().fillna(0.0)

    return out


def canonical_feature_columns() -> list[str]:
    """Return default columns expected by forecasting pipelines."""
    return [
        "latency_ms",
        "error_rate_percent",
        "cpu_usage_percent",
        "latency_x_error",
        "cpu_pressure",
        "latency_delta",
        "error_delta",
    ]
