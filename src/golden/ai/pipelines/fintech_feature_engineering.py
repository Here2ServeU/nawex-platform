# ===========================================================================
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""fintech_feature_engineering.py

Feature engineering pipeline for fintech transaction data.
Transforms raw transaction records into ML-ready features for
fraud detection and payment reliability models.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def engineer_transaction_features(
    transactions: pd.DataFrame,
    lookback_hours: int = 24,
) -> pd.DataFrame:
    """
    Generate ML features from raw transaction data.

    Creates temporal, behavioral, and statistical features used by
    the fraud detection and anomaly models.

    Args:
        transactions: DataFrame with columns: account_id, amount, timestamp,
                      merchant_category_code, channel, country_code, currency.
        lookback_hours: Window for historical feature computation.

    Returns:
        DataFrame enriched with engineered features.
    """
    if transactions.empty:
        logger.warning("Empty transactions DataFrame. Returning as-is.")
        return transactions

    df = transactions.copy()
    df = df.sort_values(["account_id", "timestamp"])

    # --- Temporal Features ---
    df["hour_of_day"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["is_night"] = df["hour_of_day"].isin(range(0, 6)).astype(int)

    # --- Per-Account Rolling Features ---
    for window in [5, 20, 50]:
        col_prefix = f"rolling_{window}"
        df[f"{col_prefix}_mean"] = df.groupby("account_id")["amount"].transform(
            lambda x, window=window: x.rolling(window, min_periods=1).mean()
        )
        df[f"{col_prefix}_std"] = df.groupby("account_id")["amount"].transform(
            lambda x, window=window: x.rolling(window, min_periods=1).std().fillna(0)
        )
        df[f"{col_prefix}_max"] = df.groupby("account_id")["amount"].transform(
            lambda x, window=window: x.rolling(window, min_periods=1).max()
        )

    # --- Amount Deviation Features ---
    df["amount_to_rolling20_ratio"] = df["amount"] / (df["rolling_20_mean"] + 1e-9)
    df["amount_zscore"] = (df["amount"] - df["rolling_20_mean"]) / (df["rolling_20_std"] + 1e-9)

    # --- Velocity Features ---
    df["time_since_last_txn"] = df.groupby("account_id")["timestamp"].diff().dt.total_seconds().fillna(3600)
    df["txn_count_1h"] = df.groupby("account_id")["timestamp"].transform(lambda x: x.rolling("1h").count())
    df["txn_count_24h"] = df.groupby("account_id")["timestamp"].transform(lambda x: x.rolling("24h").count())

    # --- Merchant Category Features ---
    df["mcc_str"] = df["merchant_category_code"].astype(str)
    high_risk_mcc = {"7995", "5967", "5966", "6051", "4829", "7801", "7802"}
    df["is_high_risk_mcc"] = df["mcc_str"].isin(high_risk_mcc).astype(int)

    # --- Channel Encoding ---
    channel_risk_map = {
        "card_not_present": 4,
        "online": 3,
        "mobile": 2,
        "atm": 1,
        "pos": 0,
    }
    df["channel_risk_level"] = df["channel"].map(channel_risk_map).fillna(2)

    # --- Geographic Features ---
    high_risk_countries = {"NG", "RU", "CN", "BR", "ID", "VN", "PH"}
    df["is_high_risk_country"] = df["country_code"].isin(high_risk_countries).astype(int)

    # --- Cross-Border Detection ---
    df["prev_country"] = df.groupby("account_id")["country_code"].shift(1)
    df["is_cross_border"] = (df["country_code"] != df["prev_country"]).astype(int)
    df["is_cross_border"] = df["is_cross_border"].where(df["prev_country"].notna(), 0)

    # Cleanup temporary columns
    df.drop(columns=["mcc_str", "prev_country"], inplace=True, errors="ignore")

    feature_cols = [c for c in df.columns if c not in transactions.columns]
    logger.info(
        f"Feature engineering complete: {len(feature_cols)} features generated "
        f"for {df['account_id'].nunique()} accounts, {len(df)} transactions."
    )

    return df


def engineer_payment_latency_features(
    latencies: pd.DataFrame,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    Generate features from payment gateway latency data.

    Args:
        latencies: DataFrame with columns: timestamp, latency_ms, gateway_id,
                   status_code, request_type.
        windows: Rolling window sizes for feature computation.

    Returns:
        DataFrame enriched with latency trend features.
    """
    if latencies.empty:
        return latencies

    windows = windows or [10, 30, 100]
    df = latencies.copy()
    df = df.sort_values("timestamp")

    for w in windows:
        df[f"latency_rolling_{w}_mean"] = df["latency_ms"].rolling(w, min_periods=1).mean()
        df[f"latency_rolling_{w}_p95"] = df["latency_ms"].rolling(w, min_periods=1).quantile(0.95)
        df[f"latency_rolling_{w}_std"] = df["latency_ms"].rolling(w, min_periods=1).std().fillna(0)

    # Error rate features
    if "status_code" in df.columns:
        df["is_error"] = (~df["status_code"].between(200, 299)).astype(int)
        for w in windows:
            df[f"error_rate_{w}"] = df["is_error"].rolling(w, min_periods=1).mean()

    # Latency trend (slope)
    if len(df) >= 10:
        df["latency_trend"] = (
            df["latency_ms"]
            .rolling(10, min_periods=5)
            .apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) >= 2 else 0.0, raw=False)
        )
    else:
        df["latency_trend"] = 0.0

    logger.info(f"Payment latency features: {len(df)} records, windows={windows}")

    return df
