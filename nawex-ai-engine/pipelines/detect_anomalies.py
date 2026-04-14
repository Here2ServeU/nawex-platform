# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
"""detect_anomalies.py

Simple z-score based anomaly detection for time-series metrics.
"""

from __future__ import annotations

import pandas as pd


def zscore_anomalies(
    df: pd.DataFrame,
    value_col: str,
    window: int = 24,
    threshold: float = 3.0,
    flag_col: str | None = None,
) -> pd.DataFrame:
    """Mark anomalies when rolling z-score exceeds threshold."""
    flag_col = flag_col or f"{value_col}_anomaly"

    rolling_mean = df[value_col].rolling(window).mean()
    rolling_std = df[value_col].rolling(window).std()

    z = (df[value_col] - rolling_mean) / (rolling_std + 1e-9)
    df[flag_col] = z.abs() > threshold
    return df
