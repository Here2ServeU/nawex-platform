# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
"""detect_fraud.py

Real-time transaction fraud detection using statistical and ML-based methods.
Designed for fintech payment processing pipelines within the Express-Reliability
AIOps Platform.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def calculate_fraud_score(transaction: Dict[str, Any], history: Optional[pd.DataFrame] = None) -> float:
    """
    Calculate a composite fraud probability score for a single transaction.

    The score combines multiple risk signals:
    - Velocity: Unusual transaction frequency for the account.
    - Amount: Statistical outlier compared to account history.
    - Geography: Impossible travel or high-risk jurisdiction.
    - Behavioral: Deviation from established spending patterns.

    Args:
        transaction: Dict with keys: account_id, amount, currency, merchant_category,
                     timestamp, source_ip, geo_lat, geo_lon, channel.
        history: Optional DataFrame of recent transactions for the account.

    Returns:
        Float between 0.0 (legitimate) and 1.0 (fraudulent).
    """
    scores: List[float] = []

    # --- Amount Anomaly Score ---
    amount = transaction.get('amount', 0)
    if history is not None and len(history) > 10:
        mean_amt = history['amount'].mean()
        std_amt = history['amount'].std()
        if std_amt > 0:
            z_amount = abs(amount - mean_amt) / std_amt
            scores.append(min(z_amount / 5.0, 1.0)) # Normalize to [0, 1]
        else:
            scores.append(0.5 if amount > mean_amt * 2 else 0.0)
    else:
        # No history: moderate baseline risk for new accounts
        scores.append(0.3)

    # --- Velocity Score ---
    if history is not None and len(history) > 0:
        recent_window = pd.Timestamp.now() - pd.Timedelta(hours=1)
        recent_txns = history[history['timestamp'] > recent_window]
        velocity = len(recent_txns)
        # More than 10 transactions per hour is suspicious
        velocity_score = min(velocity / 15.0, 1.0)
        scores.append(velocity_score)
    else:
        scores.append(0.1)

    # --- Geographic Risk Score ---
    geo_risk_countries = {'NG', 'RU', 'CN', 'BR', 'ID', 'VN', 'PH'}
    country = transaction.get('country_code', '')
    if country in geo_risk_countries:
        scores.append(0.6)
    else:
        scores.append(0.0)

    # --- Channel Risk Score ---
    channel = transaction.get('channel', 'pos')
    channel_risk = {
        'card_not_present': 0.4,
        'online': 0.3,
        'mobile': 0.2,
        'pos': 0.1,
        'atm': 0.15,
    }
    scores.append(channel_risk.get(channel, 0.2))

    # --- Merchant Category Risk ---
    high_risk_mcc = {'7995', '5967', '5966', '6051', '4829'} # Gambling, crypto, money transfer
    mcc = str(transaction.get('merchant_category_code', ''))
    if mcc in high_risk_mcc:
        scores.append(0.5)
    else:
        scores.append(0.0)

    # Weighted composite score
    weights = [0.30, 0.25, 0.15, 0.15, 0.15]
    composite = sum(s * w for s, w in zip(scores, weights))

    logger.info(
        f"Fraud score for account {transaction.get('account_id', 'unknown')}: "
        f"{composite:.4f} (amount={scores[0]:.2f}, velocity={scores[1]:.2f}, "
        f"geo={scores[2]:.2f}, channel={scores[3]:.2f}, mcc={scores[4]:.2f})"
    )

    return round(composite, 4)


def detect_transaction_anomalies(
    transactions: pd.DataFrame,
    threshold: float = 0.75,
) -> pd.DataFrame:
    """
    Batch anomaly detection across a DataFrame of transactions.

    Uses rolling statistics and z-score analysis to flag anomalous transactions
    based on amount, velocity, and temporal patterns.

    Args:
        transactions: DataFrame with columns: account_id, amount, timestamp, currency.
        threshold: Fraud score threshold above which transactions are flagged.

    Returns:
        DataFrame with added columns: fraud_score, is_flagged.
    """
    if transactions.empty:
        logger.warning("Empty transaction DataFrame received. Returning as-is.")
        transactions['fraud_score'] = pd.Series(dtype=float)
        transactions['is_flagged'] = pd.Series(dtype=bool)
        return transactions

    results = []

    for account_id, group in transactions.groupby('account_id'):
        group = group.sort_values('timestamp')

        # Rolling amount statistics
        group['rolling_mean'] = group['amount'].rolling(window=20, min_periods=1).mean()
        group['rolling_std'] = group['amount'].rolling(window=20, min_periods=1).std().fillna(1)
        group['amount_zscore'] = (group['amount'] - group['rolling_mean']) / (group['rolling_std'] + 1e-9)

        # Velocity: transactions per hour
        group['hour'] = group['timestamp'].dt.floor('h')
        velocity = group.groupby('hour')['amount'].transform('count')
        group['velocity_score'] = (velocity / 15.0).clip(upper=1.0)

        # Composite fraud score
        group['fraud_score'] = (
            0.40 * (group['amount_zscore'].abs() / 5.0).clip(upper=1.0)
            + 0.35 * group['velocity_score']
            + 0.25 * 0.1 # Baseline channel/geo risk (simplified for batch)
        ).round(4)

        group['is_flagged'] = group['fraud_score'] > threshold
        results.append(group)

    result = pd.concat(results)

    flagged_count = result['is_flagged'].sum()
    total_count = len(result)
    logger.info(
        f"Transaction anomaly detection complete: {flagged_count}/{total_count} "
        f"flagged ({flagged_count / total_count * 100:.1f}%) at threshold {threshold}"
    )

    return result


def detect_payment_latency_risk(
    latencies: pd.DataFrame,
    slo_ms: float = 100.0,
    window: int = 30,
    breach_ratio: float = 0.05,
) -> Dict[str, Any]:
    """
    Detect payment processing latency SLO breaches.

    Monitors rolling payment gateway response times and flags when the
    percentage of SLO-breaching transactions exceeds the allowed ratio.

    Args:
        latencies: DataFrame with columns: timestamp, latency_ms, gateway_id.
        slo_ms: Target payment processing latency SLO in milliseconds.
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

    if rolling_breach_pct > 0.20:
        level = 'critical'
        recommendation = 'failover_payment_gateway'
    elif rolling_breach_pct > 0.10:
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
        f"Payment latency risk: {level} | breach={rolling_breach_pct:.1%} | "
        f"avg={avg_latency:.1f}ms | p99={p99_latency:.1f}ms"
    )

    return result


def detect_settlement_risk(
    settlement_data: pd.DataFrame,
    max_processing_minutes: float = 120.0,
) -> Dict[str, Any]:
    """
    Detect settlement processing delays that may breach clearing windows.

    Args:
        settlement_data: DataFrame with columns: batch_id, start_time, current_progress_pct,
                         estimated_completion_minutes.
        max_processing_minutes: Maximum allowed processing time before escalation.

    Returns:
        Dict with risk assessment including at-risk batches and recommendations.
    """
    if settlement_data.empty:
        return {'level': 'low', 'at_risk_batches': [], 'recommendation': 'none'}

    at_risk = settlement_data[
        settlement_data['estimated_completion_minutes'] > max_processing_minutes
    ]

    if len(at_risk) > 0:
        level = 'critical' if len(at_risk) > 3 else 'high'
        recommendation = 'halt_settlement'
    else:
        level = 'low'
        recommendation = 'none'

    result = {
        'level': level,
        'at_risk_batches': at_risk['batch_id'].tolist() if len(at_risk) > 0 else [],
        'total_batches': len(settlement_data),
        'recommendation': recommendation,
    }

    logger.info(
        f"Settlement risk: {level} | {len(at_risk)}/{len(settlement_data)} batches at risk"
    )

    return result
