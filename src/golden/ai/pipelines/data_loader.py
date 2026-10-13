"""Load time-series SLI/SLO data from CSV or a seeded synthetic generator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def load_timeseries_csv(
    path: str | Path,
    timestamp_col: str = "timestamp",
    parse_dates: bool = True,
    tz: str | None = None,
) -> pd.DataFrame:
    """Load a CSV file as a DataFrame sorted by ``timestamp_col``."""
    df = pd.read_csv(path)
    if parse_dates:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        if tz:
            df[timestamp_col] = df[timestamp_col].dt.tz_localize(tz)
    return df.sort_values(timestamp_col).reset_index(drop=True)


def load_sample_sli_slo(n_points: int = 500, freq: str = "5min", seed: int | None = 42) -> pd.DataFrame:
    """Synthetic SLI/SLO telemetry: seasonal latency (~150 ms) with noise and occasional spikes."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2025-01-01", periods=n_points, freq=freq)
    t = np.linspace(0, 20, n_points)
    latency = 150 + 20 * np.sin(t) + rng.normal(0, 5, n_points)
    spikes = rng.random(n_points) < 0.02
    latency[spikes] += rng.uniform(40, 90, spikes.sum())
    return pd.DataFrame(
        {
            "timestamp": index,
            "latency_ms": latency,
            "error_rate": 0.2 + 0.8 * rng.random(n_points),
            "slo_latency_ms": 200.0,
            "slo_error_rate": 1.0,
        }
    )
