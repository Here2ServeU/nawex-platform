"""Synthetic dataset generators for local demos and testing."""

from __future__ import annotations

import importlib
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Literal


def _resolve_step_minutes(freq: str) -> int:
    if freq.endswith("min"):
        return int(freq.replace("min", ""))
    return 5


def _pandas_dataframe(records):
    pd = importlib.import_module("pandas")
    return pd.DataFrame.from_records(records)


def make_sli_dataset(n_rows: int = 500, freq: str = "5min"):
    """Generate synthetic SLI telemetry for reliability demos."""
    step = _resolve_step_minutes(freq)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    records = []

    for i in range(n_rows):
        t = start + timedelta(minutes=i * step)
        trend = i / max(1, n_rows - 1)
        latency = 130 + 35 * math.sin(i * 18 / max(n_rows, 1)) + 40 * trend + random.gauss(0, 5)
        error_rate = max(0.0, min(100.0, 0.1 + 0.7 * random.random() + 0.2 * trend))
        cpu = max(0.0, min(100.0, 50 + 20 * math.sin(i * 12 / max(n_rows, 1)) + random.gauss(0, 4)))
        records.append(
            {
                "timestamp": t,
                "latency_ms": round(latency, 2),
                "error_rate_percent": round(error_rate, 3),
                "cpu_usage_percent": round(cpu, 2),
                "slo_latency_ms": 200.0,
                "slo_error_rate_percent": 1.0,
            }
        )

    return _pandas_dataframe(records)


def make_transactions_dataset(n_rows: int = 1200, mode: Literal["mixed", "mostly_clean"] = "mixed"):
    """Generate synthetic fintech transactions with controllable anomaly ratio."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    records = []
    countries = ["US", "CA", "GB", "NG", "BR"]
    channels = ["online", "pos", "card_not_present", "mobile"]
    mccs = ["5411", "5732", "7995", "4829", "6011"]

    for i in range(n_rows):
        ts = now - timedelta(minutes=(n_rows - i - 1))
        amount = random.lognormvariate(3.2, 0.55)
        if mode == "mixed" and random.random() < 0.05:
            amount += random.uniform(250, 2500)

        records.append(
            {
                "transaction_id": f"txn-{i:06d}",
                "account_id": f"acct-{random.randint(1, 80):03d}",
                "timestamp": ts,
                "amount": round(amount, 2),
                "country_code": random.choice(countries),
                "channel": random.choice(channels),
                "merchant_category_code": random.choice(mccs),
            }
        )

    return _pandas_dataframe(records)
