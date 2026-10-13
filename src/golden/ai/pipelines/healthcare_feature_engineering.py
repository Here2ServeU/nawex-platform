# ===========================================================================
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""healthcare_feature_engineering.py

Feature engineering for healthcare clinical data pipelines.
Transforms raw EHR events, vital signs, and PHI access logs into
ML-ready feature vectors for the clinical anomaly detection models.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def engineer_vitals_features(vitals: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features from patient vital signs for clinical anomaly detection.

    Computes rolling statistics, rate-of-change indicators, and composite
    clinical severity scores from raw vital sign data.

    Args:
        vitals: DataFrame with columns: patient_id, timestamp, heart_rate,
                spo2, systolic_bp, diastolic_bp, temperature, respiratory_rate.

    Returns:
        DataFrame with engineered features appended.
    """
    if vitals.empty:
        logger.warning("Empty vitals DataFrame. Returning as-is.")
        return vitals

    result = vitals.copy()
    result = result.sort_values(["patient_id", "timestamp"])

    for col in ["heart_rate", "spo2", "systolic_bp", "temperature", "respiratory_rate"]:
        if col not in result.columns:
            continue

        # Rolling statistics (per patient)
        result[f"{col}_rolling_mean"] = result.groupby("patient_id")[col].transform(
            lambda x: x.rolling(window=10, min_periods=1).mean()
        )
        result[f"{col}_rolling_std"] = result.groupby("patient_id")[col].transform(
            lambda x: x.rolling(window=10, min_periods=1).std().fillna(0)
        )

        # Z-score relative to patient baseline
        result[f"{col}_zscore"] = (result[col] - result[f"{col}_rolling_mean"]) / (
            result[f"{col}_rolling_std"] + 1e-9
        )

        # Rate of change (first derivative)
        result[f"{col}_delta"] = result.groupby("patient_id")[col].diff().fillna(0)

    # Composite Early Warning Score (NEWS-inspired)
    if all(
        c in result.columns for c in ["heart_rate", "spo2", "systolic_bp", "temperature", "respiratory_rate"]
    ):
        result["ews_score"] = (
            np.where(
                result["heart_rate"] > 130,
                3,
                np.where(result["heart_rate"] > 110, 2, np.where(result["heart_rate"] > 90, 1, 0)),
            )
            + np.where(
                result["spo2"] < 92, 3, np.where(result["spo2"] < 94, 2, np.where(result["spo2"] < 96, 1, 0))
            )
            + np.where(
                result["systolic_bp"] < 90,
                3,
                np.where(result["systolic_bp"] < 100, 2, np.where(result["systolic_bp"] > 180, 3, 0)),
            )
            + np.where(
                result["temperature"] > 39.0,
                2,
                np.where(result["temperature"] < 35.0, 3, np.where(result["temperature"] > 38.0, 1, 0)),
            )
            + np.where(
                result["respiratory_rate"] > 25,
                3,
                np.where(result["respiratory_rate"] > 20, 2, np.where(result["respiratory_rate"] < 9, 3, 0)),
            )
        )

    logger.info(
        f"Vitals feature engineering complete: {len(result)} records, "
        f"{result['patient_id'].nunique()} patients"
    )

    return result


def engineer_phi_access_features(access_logs: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features from PHI access logs for insider threat and breach detection.

    Computes behavioral baselines, access velocity, and anomaly indicators
    from raw audit logs.

    Args:
        access_logs: DataFrame with columns: user_id, timestamp, patient_id,
                     department, access_type, record_count.

    Returns:
        DataFrame with engineered features appended.
    """
    if access_logs.empty:
        logger.warning("Empty PHI access log DataFrame. Returning as-is.")
        return access_logs

    result = access_logs.copy()
    result = result.sort_values(["user_id", "timestamp"])

    # Access volume features
    result["volume_rolling_mean"] = result.groupby("user_id")["record_count"].transform(
        lambda x: x.rolling(window=20, min_periods=1).mean()
    )
    result["volume_rolling_std"] = result.groupby("user_id")["record_count"].transform(
        lambda x: x.rolling(window=20, min_periods=1).std().fillna(1)
    )
    result["volume_zscore"] = (result["record_count"] - result["volume_rolling_mean"]) / (
        result["volume_rolling_std"] + 1e-9
    )

    # Access velocity (events per hour per user)
    result["hour"] = result["timestamp"].dt.floor("h")
    result["access_velocity"] = result.groupby(["user_id", "hour"])["record_count"].transform("count")

    # Unique patients accessed per session
    result["unique_patients_accessed"] = result.groupby("user_id")["patient_id"].transform(
        lambda x: x.expanding().apply(lambda s: s.nunique(), raw=False)
    )

    # Temporal features
    result["hour_of_day"] = result["timestamp"].dt.hour
    result["day_of_week"] = result["timestamp"].dt.dayofweek
    result["is_after_hours"] = result["hour_of_day"].apply(lambda h: h < 7 or h > 19)
    result["is_weekend"] = result["day_of_week"].apply(lambda d: d >= 5)

    # Access type encoding
    access_risk_map = {
        "bulk_export": 5,
        "print": 4,
        "copy": 3,
        "write": 2,
        "search": 1,
        "read": 0,
    }
    result["access_risk_level"] = result["access_type"].map(access_risk_map).fillna(1)

    logger.info(
        f"PHI access feature engineering complete: {len(result)} events, {result['user_id'].nunique()} users"
    )

    return result


def engineer_ehr_latency_features(latencies: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features from EHR query latencies for performance monitoring.

    Args:
        latencies: DataFrame with columns: timestamp, latency_ms, endpoint,
                   department, query_type.

    Returns:
        DataFrame with engineered features appended.
    """
    if latencies.empty:
        logger.warning("Empty latency DataFrame. Returning as-is.")
        return latencies

    result = latencies.copy()
    result = result.sort_values("timestamp")

    # Rolling latency statistics
    result["latency_rolling_mean"] = result["latency_ms"].rolling(window=30, min_periods=1).mean()
    result["latency_rolling_std"] = result["latency_ms"].rolling(window=30, min_periods=1).std().fillna(1)
    result["latency_zscore"] = (result["latency_ms"] - result["latency_rolling_mean"]) / (
        result["latency_rolling_std"] + 1e-9
    )

    # Percentile features
    result["latency_p95"] = result["latency_ms"].rolling(window=100, min_periods=1).quantile(0.95)
    result["latency_p99"] = result["latency_ms"].rolling(window=100, min_periods=1).quantile(0.99)

    # SLO breach indicator (200ms for EHR queries)
    result["slo_breach"] = result["latency_ms"] > 200.0
    result["breach_rolling_pct"] = result["slo_breach"].rolling(window=30, min_periods=1).mean()

    logger.info(
        f"EHR latency feature engineering complete: {len(result)} samples, "
        f"breach_rate={result['slo_breach'].mean():.2%}"
    )

    return result
