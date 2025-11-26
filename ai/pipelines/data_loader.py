"""data_loader.py

Loads time-series SLI/SLO data from CSV or synthetic generator.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def load_timeseries_csv(
    path: str | Path,
    timestamp_col: str = "timestamp",
    parse_dates: bool = True,
    tz: Optional[str] = None,
) -> pd.DataFrame:
    """Load a CSV file as a time-sorted DataFrame.

    Args:
        path: Path to CSV file.
        timestamp_col: Column name containing timestamps.
        parse_dates: Parse timestamp column as datetime.
        tz: Optional timezone to localize to.

    Returns:
        Sorted DataFrame by timestamp.
    """
    df = pd.read_csv(path)
    if parse_dates:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        if tz:
            df[timestamp_col] = df[timestamp_col].dt.tz_localize(tz)
    df = df.sort_values(timestamp_col).reset_index(drop=True)
    return df


def load_sample_sli_slo(n_points: int = 500, freq: str = "5min") -> pd.DataFrame:
    """Generate synthetic time-series SLI/SLO data for demos.

    Columns:
        - timestamp
        - latency_ms
        - error_rate
        - slo_latency_ms
        - slo_error_rate
    """
    rng = pd.date_range("2025-01-01", periods=n_points, freq=freq)

    # Latency around 150ms with some periodic variation and noise
    latency = 150 + 20 * np.sin(np.linspace(0, 20, len(rng))) + np.random.randn(len(rng)) * 5

    # Error rate around 0.2% to 1%
    error_rate = 0.2 + 0.8 * np.random.rand(len(rng))

    df = pd.DataFrame(
        {
            "timestamp": rng,
            "latency_ms": latency,
            "error_rate": error_rate,
            "slo_latency_ms": 200.0,
            "slo_error_rate": 1.0,  # 1% error allowed
        }
    )
    return df


if __name__ == "__main__":
    df = load_sample_sli_slo()
    print(df.head())
