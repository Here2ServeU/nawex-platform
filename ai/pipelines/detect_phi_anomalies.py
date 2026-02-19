# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
"""detect_phi_anomalies.py

Real-time PHI (Protected Health Information) access anomaly detection and
clinical event monitoring for the Express-Reliability Healthcare vertical.
Designed for HIPAA-compliant EHR processing pipelines.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calculate_phi_risk_score(access_event: Dict[str, Any], history: Optional[pd.DataFrame] = None) -> float:
    """
    Calculate a composite PHI access risk score for a single access event.

    The score combines multiple risk signals:
    - Volume: Unusual number of records accessed in a time window.
    - Pattern: Deviation from established access patterns for the user/role.
    - Temporal: After-hours or weekend access patterns.
    - Scope: Cross-department or cross-facility access.

    Args:
        access_event: Dict with keys: user_id, role, department, patient_id,
                      access_type, timestamp, record_count, is_after_hours.
        history: Optional DataFrame of recent access events for the user.

    Returns:
        Float between 0.0 (normal) and 1.0 (highly anomalous).
    """
    scores: List[float] = []

    # --- Access Volume Anomaly ---
    record_count = access_event.get('record_count', 1)
    if history is not None and len(history) > 10:
        mean_count = history['record_count'].mean()
        std_count = history['record_count'].std()
        if std_count > 0:
            z_volume = abs(record_count - mean_count) / std_count
            scores.append(min(z_volume / 4.0, 1.0))
        else:
            scores.append(0.5 if record_count > mean_count * 3 else 0.0)
    else:
        # No history: moderate baseline for new users
        scores.append(0.2 if record_count > 10 else 0.05)

    # --- Temporal Risk ---
    is_after_hours = access_event.get('is_after_hours', False)
    is_weekend = access_event.get('is_weekend', False)
    temporal_score = 0.0
    if is_after_hours:
        temporal_score += 0.30
    if is_weekend:
        temporal_score += 0.20
    scores.append(min(temporal_score, 1.0))

    # --- Cross-Department Access ---
    cross_dept = access_event.get('cross_department', False)
    if cross_dept:
        scores.append(0.40)
    else:
        scores.append(0.0)

    # --- Access Type Risk ---
    access_type = access_event.get('access_type', 'read')
    access_risk = {
        'bulk_export': 0.60,
        'print': 0.35,
        'copy': 0.30,
        'write': 0.15,
        'read': 0.05,
        'search': 0.10,
    }
    scores.append(access_risk.get(access_type, 0.10))

    # --- Role Appropriateness ---
    role = access_event.get('role', 'clinician')
    role_risk = {
        'admin': 0.15,
        'it_support': 0.25,
        'researcher': 0.20,
        'contractor': 0.35,
        'clinician': 0.05,
        'nurse': 0.05,
        'pharmacist': 0.08,
    }
    scores.append(role_risk.get(role, 0.15))

    # Weighted composite score
    weights = [0.30, 0.20, 0.20, 0.15, 0.15]
    composite = sum(s * w for s, w in zip(scores, weights))

    logger.info(
        f"PHI risk score for user {access_event.get('user_id', 'unknown')}: "
        f"{composite:.4f} (volume={scores[0]:.2f}, temporal={scores[1]:.2f}, "
        f"cross_dept={scores[2]:.2f}, access_type={scores[3]:.2f}, role={scores[4]:.2f})"
    )

    return round(composite, 4)


def detect_phi_access_anomalies(
    access_logs: pd.DataFrame,
    threshold: float = 0.60,
) -> pd.DataFrame:
    """
    Batch anomaly detection across a DataFrame of PHI access events.

    Uses rolling statistics and z-score analysis to flag anomalous access
    patterns based on volume, timing, and behavioral signals.

    Args:
        access_logs: DataFrame with columns: user_id, record_count, timestamp,
                     department, access_type, role.
        threshold: Risk score threshold above which events are flagged.

    Returns:
        DataFrame with added columns: phi_risk_score, is_flagged.
    """
    if access_logs.empty:
        logger.warning("Empty access log DataFrame received. Returning as-is.")
        access_logs['phi_risk_score'] = pd.Series(dtype=float)
        access_logs['is_flagged'] = pd.Series(dtype=bool)
        return access_logs

    results = []

    for user_id, group in access_logs.groupby('user_id'):
        group = group.sort_values('timestamp')

        # Rolling volume statistics
        group['rolling_mean'] = group['record_count'].rolling(window=20, min_periods=1).mean()
        group['rolling_std'] = group['record_count'].rolling(window=20, min_periods=1).std().fillna(1)
        group['volume_zscore'] = (group['record_count'] - group['rolling_mean']) / (group['rolling_std'] + 1e-9)

        # Access frequency: events per hour
        group['hour'] = group['timestamp'].dt.floor('h')
        frequency = group.groupby('hour')['record_count'].transform('count')
        group['frequency_score'] = (frequency / 10.0).clip(upper=1.0)

        # Composite PHI risk score
        group['phi_risk_score'] = (
            0.40 * (group['volume_zscore'].abs() / 4.0).clip(upper=1.0)
            + 0.35 * group['frequency_score']
            + 0.25 * 0.1 # Baseline role/temporal risk (simplified for batch)
        ).round(4)

        group['is_flagged'] = group['phi_risk_score'] > threshold
        results.append(group)

    result = pd.concat(results)

    flagged_count = result['is_flagged'].sum()
    total_count = len(result)
    logger.info(
        f"PHI access anomaly detection complete: {flagged_count}/{total_count} "
        f"flagged ({flagged_count / total_count * 100:.1f}%) at threshold {threshold}"
    )

    return result


def detect_clinical_latency_risk(
    latencies: pd.DataFrame,
    slo_ms: float = 200.0,
    window: int = 30,
    breach_ratio: float = 0.03,
) -> Dict[str, Any]:
    """
    Detect EHR query latency SLO breaches.

    Monitors rolling clinical data gateway response times and flags when the
    percentage of SLO-breaching requests exceeds the allowed ratio.

    Args:
        latencies: DataFrame with columns: timestamp, latency_ms, endpoint.
        slo_ms: Target EHR query latency SLO in milliseconds.
        window: Rolling window size for breach ratio calculation.
        breach_ratio: Maximum allowed ratio of SLO breaches before alerting.

    Returns:
        Dict with risk assessment: level, breach_pct, avg_latency, recommendation.
    """
    if latencies.empty:
        return {'level': 'low', 'breach_pct': 0.0, 'avg_latency': 0.0, 'recommendation': 'none'}

    breaches = latencies['latency_ms'] > slo_ms
    rolling_breach_pct = breaches.rolling(window).mean().iloc[-1] if len(breaches) >= window else breaches.mean()
    avg_latency = latencies['latency_ms'].mean()
    p99_latency = latencies['latency_ms'].quantile(0.99)

    if rolling_breach_pct > 0.15:
        level = 'critical'
        recommendation = 'failover_ehr_gateway'
    elif rolling_breach_pct > 0.08:
        level = 'high'
        recommendation = 'scale_up_replicas'
    elif rolling_breach_pct > breach_ratio:
        level = 'medium'
        recommendation = 'investigate'
    else:
        level = 'low'
        recommendation = 'none'

    result = {
        'level': level,
        'breach_pct': round(float(rolling_breach_pct), 4),
        'avg_latency': round(float(avg_latency), 2),
        'p99_latency': round(float(p99_latency), 2),
        'slo_ms': slo_ms,
        'recommendation': recommendation,
    }

    logger.info(
        f"Clinical latency risk: {level} | breach={rolling_breach_pct:.1%} | "
        f"avg={avg_latency:.1f}ms | p99={p99_latency:.1f}ms"
    )

    return result


def detect_patient_safety_risk(
    vitals_data: pd.DataFrame,
    critical_thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Detect patient safety risks from aggregated vitals telemetry.

    Args:
        vitals_data: DataFrame with columns: patient_id, heart_rate, spo2,
                     systolic_bp, temperature, department, timestamp.
        critical_thresholds: Override default clinical alert thresholds.

    Returns:
        Dict with risk assessment including at-risk patients and recommendations.
    """
    if vitals_data.empty:
        return {'level': 'low', 'at_risk_patients': [], 'recommendation': 'none'}

    if critical_thresholds is None:
        critical_thresholds = {
            'heart_rate_high': 130,
            'heart_rate_low': 45,
            'spo2_critical': 88,
            'systolic_bp_high': 190,
            'systolic_bp_low': 80,
            'temperature_high': 39.5,
            'temperature_low': 34.5,
        }

    at_risk = vitals_data[
        (vitals_data['heart_rate'] > critical_thresholds['heart_rate_high']) |
        (vitals_data['heart_rate'] < critical_thresholds['heart_rate_low']) |
        (vitals_data['spo2'] < critical_thresholds['spo2_critical']) |
        (vitals_data['systolic_bp'] > critical_thresholds['systolic_bp_high']) |
        (vitals_data['systolic_bp'] < critical_thresholds['systolic_bp_low']) |
        (vitals_data['temperature'] > critical_thresholds['temperature_high']) |
        (vitals_data['temperature'] < critical_thresholds['temperature_low'])
    ]

    if len(at_risk) > 0:
        level = 'critical' if len(at_risk) > 5 else 'high'
        recommendation = 'escalate_clinical_alert'
    else:
        level = 'low'
        recommendation = 'none'

    result = {
        'level': level,
        'at_risk_patients': at_risk['patient_id'].unique().tolist() if len(at_risk) > 0 else [],
        'total_patients_monitored': vitals_data['patient_id'].nunique(),
        'recommendation': recommendation,
    }

    logger.info(
        f"Patient safety risk: {level} | "
        f"{len(at_risk)} critical events across {len(result['at_risk_patients'])} patients"
    )

    return result
