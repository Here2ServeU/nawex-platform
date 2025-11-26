"""feature_engineering.py

Feature construction for time-series SLI/SLO prediction.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
import pandas as pd


def add_rolling_features(
    df: pd.DataFrame,
    value_col: str,
    window: int = 12,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Adds rolling mean/std features for a given metric column."""
    prefix = prefix or value_col
    df[f"{prefix}_roll_mean_{window}"] = df[value_col].rolling(window).mean()
    df[f"{prefix}_roll_std_{window}"] = df[value_col].rolling(window).std()
    return df


def build_supervised_sequences(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    lookback: int = 24,
    horizon: int = 6,
) -> Tuple[np.ndarray, np.ndarray]:
    """Convert time series into supervised learning sequences.

    Args:
        df: DataFrame with time-ordered rows.
        feature_cols: Input feature columns.
        target_col: Target column to predict.
        lookback: Number of past steps to use as input.
        horizon: Forecast horizon length.

    Returns:
        X: (n_samples, lookback, n_features)
        y: (n_samples, horizon)
    """
    df_clean = df[feature_cols + [target_col]].dropna()
    values = df_clean.values

    X, y = [], []
    for i in range(len(values) - lookback - horizon):
        X.append(values[i : i + lookback, :-1])
        y.append(values[i + lookback : i + lookback + horizon, -1])
    return np.array(X), np.array(y)
