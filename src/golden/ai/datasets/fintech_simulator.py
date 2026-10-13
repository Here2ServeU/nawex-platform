# ===========================================================================
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""fintech_simulator.py

Generates realistic synthetic financial transaction data for the platform demos.

All data is fully synthetic — no real account numbers, card data, or
personally identifiable information. Designed to demonstrate the platform's
real-time fraud detection and payment reliability AI capabilities to
bank risk officers and compliance teams.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

_RNG = np.random.default_rng(seed=42)
_CHANNELS = ["pos", "online", "mobile", "card_not_present", "atm"]
_CURRENCIES = ["USD", "EUR", "GBP", "CAD", "MXN"]
_HIGH_RISK_MCC = ["7995", "5967", "6051", "4829"]
_NORMAL_MCC = ["5411", "5812", "5912", "7011", "5912", "5511", "5732", "8049"]
_FRAUD_TYPES = [
    "card_not_present",
    "account_takeover",
    "synthetic_identity",
    "velocity_abuse",
    "geo_impossible",
]
_COUNTRIES_NORMAL = ["US", "CA", "GB", "DE", "FR", "AU", "JP"]
_COUNTRIES_HIGH_RISK = ["NG", "RU", "CN", "BR", "ID", "VN", "PH"]
_GATEWAY_IDS = ["GW-001", "GW-002", "GW-003"]


def make_fraud_scenario_stream(
    n_transactions: int = 500,
    scenario: str = "mixed",
    fraud_rate: float = 0.04,
    seed: int | None = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic transaction stream for fraud detection demo.

    Scenarios:
    - "clean": Normal traffic with background fraud rate
    - "fraud_burst": Concentrated burst attack (velocity abuse pattern)
    - "mixed": Normal traffic with several distinct fraud injection events

    Args:
        n_transactions: Total number of transactions to generate
        scenario: "clean" | "fraud_burst" | "mixed"
        fraud_rate: Base fraud rate (overridden for burst scenario)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: transaction_id, account_id, amount, currency,
        channel, country_code, merchant_category_code, timestamp, fraud_score,
        is_fraud, fraud_type, estimated_loss_usd, detection_method, risk_level
    """
    rng = np.random.default_rng(seed)
    base_time = datetime.now() - timedelta(hours=4)

    if scenario == "fraud_burst":
        fraud_rate = max(fraud_rate, 0.12)

    n_accounts = max(10, n_transactions // 15)
    account_ids = [f"ACC-{rng.integers(100000, 999999)}" for _ in range(n_accounts)]

    rows = []
    for i in range(n_transactions):
        ts = base_time + timedelta(seconds=int(rng.integers(0, 4 * 3600)))
        account_id = rng.choice(account_ids)

        # Determine if this transaction is fraudulent
        is_fraud = False
        fraud_type = None
        estimated_loss = 0.0
        detection_method = "none"

        if scenario == "fraud_burst" and 0.35 < (i / n_transactions) < 0.65:
            # Burst window: elevated fraud in middle third of stream
            is_fraud = rng.random() < 0.22
        elif scenario == "mixed":
            is_fraud = rng.random() < fraud_rate
        else:
            is_fraud = rng.random() < fraud_rate * 0.5

        if is_fraud:
            fraud_type = str(rng.choice(_FRAUD_TYPES))
            amount = float(rng.uniform(500, 4500))
            channel = str(rng.choice(["card_not_present", "online"], p=[0.6, 0.4]))
            country = str(rng.choice(_COUNTRIES_HIGH_RISK))
            mcc = str(rng.choice(_HIGH_RISK_MCC))
            estimated_loss = amount * rng.uniform(0.8, 1.0)
            detection_method = str(rng.choice(["velocity_rule", "geo_anomaly", "amount_zscore", "ml_model"]))
        else:
            amount = float(rng.lognormal(mean=5.0, sigma=1.2))
            amount = float(np.clip(amount, 5, 3000))
            channel = str(rng.choice(_CHANNELS, p=[0.45, 0.25, 0.20, 0.07, 0.03]))
            country = str(rng.choice(_COUNTRIES_NORMAL))
            mcc = str(rng.choice(_NORMAL_MCC))

        # Compute fraud score (mirrors detect_fraud.py logic)
        amount_risk = min(amount / 3000.0, 1.0) * 0.30
        channel_risk_map = {"card_not_present": 0.4, "online": 0.3, "mobile": 0.2, "pos": 0.1, "atm": 0.15}
        channel_risk = channel_risk_map.get(channel, 0.2) * 0.15
        geo_risk = (0.6 if country in _COUNTRIES_HIGH_RISK else 0.0) * 0.15
        mcc_risk = (0.5 if mcc in _HIGH_RISK_MCC else 0.0) * 0.15
        base_fraud_score = amount_risk + channel_risk + geo_risk + mcc_risk + rng.uniform(0.0, 0.25) * 0.25
        fraud_score = float(np.clip(base_fraud_score + (0.35 if is_fraud else 0.0), 0.0, 1.0))

        if fraud_score > 0.75:
            risk_level = "critical"
        elif fraud_score > 0.55:
            risk_level = "high"
        elif fraud_score > 0.35:
            risk_level = "medium"
        else:
            risk_level = "low"

        rows.append(
            {
                "transaction_id": f"TXN-{i + 1:06d}",
                "account_id": account_id,
                "amount": round(amount, 2),
                "currency": rng.choice(_CURRENCIES, p=[0.70, 0.12, 0.08, 0.06, 0.04]),
                "channel": channel,
                "country_code": country,
                "merchant_category_code": mcc,
                "timestamp": ts,
                "fraud_score": round(fraud_score, 4),
                "is_fraud": is_fraud,
                "fraud_type": fraud_type,
                "estimated_loss_usd": round(estimated_loss, 2),
                "detection_method": detection_method if is_fraud else None,
                "risk_level": risk_level,
            }
        )

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def make_payment_latency_stream(
    n_gateways: int = 3,
    n_timepoints: int = 120,
    inject_degradation: bool = True,
    degradation_gateway: str = "GW-002",
    seed: int | None = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic payment gateway latency stream for SLO demo.

    Simulates realistic gateway latency with one gateway undergoing a
    degradation event (the narrative arc for the the platform AIOps demo).

    Args:
        n_gateways: Number of payment gateways to simulate
        n_timepoints: Number of time intervals (seconds between measurements)
        inject_degradation: Whether to inject a degradation event
        degradation_gateway: Which gateway experiences degradation
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: gateway_id, timestamp, latency_ms,
        success, error_code, slo_breach, p99_latency_ms
    """
    rng = np.random.default_rng(seed)
    base_time = datetime.now() - timedelta(minutes=n_timepoints * 5)
    gateway_ids = _GATEWAY_IDS[:n_gateways]
    slo_ms = 100.0

    rows = []
    for t in range(n_timepoints):
        ts = base_time + timedelta(seconds=t * 5)
        for gw in gateway_ids:
            # Normal latency: log-normal ~30ms
            base_latency = float(rng.lognormal(mean=3.4, sigma=0.4))

            # Inject degradation arc for target gateway
            if inject_degradation and gw == degradation_gateway:
                degradation_phase = t / n_timepoints
                if 0.30 < degradation_phase < 0.45:
                    # Ramp up
                    multiplier = 1.0 + (degradation_phase - 0.30) / 0.15 * 8.0
                    base_latency *= multiplier
                elif 0.45 <= degradation_phase < 0.60:
                    # Peak degradation
                    base_latency = float(rng.uniform(180, 450))
                elif 0.60 <= degradation_phase < 0.75:
                    # Recovery (the platform triggered failover)
                    multiplier = max(1.0, 8.0 - (degradation_phase - 0.60) / 0.15 * 7.0)
                    base_latency *= multiplier

            latency = float(np.clip(base_latency, 5, 600))
            success = latency < 500
            error_code = None if success else "GATEWAY_TIMEOUT"
            slo_breach = latency > slo_ms

            rows.append(
                {
                    "gateway_id": gw,
                    "timestamp": ts,
                    "latency_ms": round(latency, 2),
                    "success": success,
                    "error_code": error_code,
                    "slo_breach": slo_breach,
                    "slo_ms": slo_ms,
                }
            )

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Add p99 latency per gateway per minute window
    df["minute"] = df["timestamp"].dt.floor("min")
    p99 = df.groupby(["gateway_id", "minute"])["latency_ms"].quantile(0.99).reset_index()
    p99.columns = ["gateway_id", "minute", "p99_latency_ms"]
    df = df.merge(p99, on=["gateway_id", "minute"], how="left")
    df.drop(columns=["minute"], inplace=True)

    return df.sort_values(["timestamp", "gateway_id"]).reset_index(drop=True)


def make_settlement_batch_stream(
    n_batches: int = 20,
    seed: int | None = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic settlement batch processing stream.

    Simulates ACH/wire settlement batches with one at-risk batch
    that the platform's settlement risk detection flags.

    Args:
        n_batches: Number of settlement batches to simulate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: batch_id, start_time, estimated_completion_minutes,
        current_progress_pct, amount_usd, status, at_risk
    """
    rng = np.random.default_rng(seed)
    base_time = datetime.now() - timedelta(hours=3)
    statuses = ["processing", "processing", "processing", "completed", "pending"]

    rows = []
    for i in range(n_batches):
        start_time = base_time + timedelta(minutes=int(i * 9))
        amount = float(rng.lognormal(mean=14.5, sigma=1.2))  # ~$2M range
        amount = float(np.clip(amount, 500_000, 25_000_000))

        normal_completion_min = float(rng.uniform(30, 90))
        at_risk = False

        # Inject one at-risk batch (slow processing)
        if i == n_batches // 2:
            normal_completion_min = float(rng.uniform(130, 200))
            at_risk = True

        progress = min(100.0, float(rng.uniform(20, 95)))
        status = rng.choice(statuses)
        if progress >= 100:
            status = "completed"
            at_risk = False

        rows.append(
            {
                "batch_id": f"BATCH-{i + 1:03d}",
                "start_time": start_time,
                "estimated_completion_minutes": round(normal_completion_min, 1),
                "current_progress_pct": round(progress, 1),
                "amount_usd": round(amount, 2),
                "status": status,
                "at_risk": at_risk,
            }
        )

    df = pd.DataFrame(rows)
    df["start_time"] = pd.to_datetime(df["start_time"])
    return df
