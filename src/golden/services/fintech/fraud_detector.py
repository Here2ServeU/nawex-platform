"""Fraud detector service — explainable 5-signal fraud scoring with per-account behavioural history."""

from __future__ import annotations

import os
import threading
from collections import OrderedDict, deque
from datetime import UTC, datetime

import pandas as pd
from prometheus_client import Histogram
from pydantic import BaseModel, Field

from golden.ai.pipelines.detect_fraud import SIGNAL_WEIGHTS, fraud_signals
from golden.security.guardrails import clamp_score
from golden.services.common import create_app, run

SERVICE = "fraud-detector"
MODEL_VERSION = "fraud-signals-v2"
FRAUD_SCORE = Histogram("golden_fraud_score", "Fraud scores produced.", buckets=[i / 10 for i in range(11)])

app = create_app(SERVICE, "Real-time explainable fraud scoring (amount, velocity, geo, channel, MCC).")

_MAX_ACCOUNTS = 10_000
_MAX_HISTORY = 200
_history: OrderedDict[str, deque[tuple[datetime, float]]] = OrderedDict()
_lock = threading.Lock()


class Transaction(BaseModel):
    transaction_id: str = Field("unknown", max_length=128)
    account_id: str = Field("anonymous", max_length=128)
    amount: float = Field(..., ge=0, le=10_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    channel: str = Field("online", max_length=32)
    country_code: str = Field("US", min_length=2, max_length=2)
    merchant_category_code: str = Field("0000", max_length=4)


def _risk_level(score: float) -> str:
    if score > 0.75:
        return "critical"
    if score > 0.55:
        return "high"
    if score > 0.35:
        return "medium"
    return "low"


def reset_state() -> None:
    with _lock:
        _history.clear()


@app.post("/score")
def score(txn: Transaction) -> dict:
    now = datetime.now(UTC)
    with _lock:
        events = _history.get(txn.account_id)
        frame = (
            pd.DataFrame(
                {
                    "timestamp": pd.to_datetime([t for t, _ in events], utc=True),
                    "amount": [a for _, a in events],
                }
            )
            if events
            else None
        )
    signals = fraud_signals(txn.model_dump(), frame, now=pd.Timestamp(now))
    fraud_score = clamp_score(sum(signals[k] * w for k, w in SIGNAL_WEIGHTS.items()))

    with _lock:
        events = _history.setdefault(txn.account_id, deque(maxlen=_MAX_HISTORY))
        events.append((now, txn.amount))
        _history.move_to_end(txn.account_id)
        while len(_history) > _MAX_ACCOUNTS:
            _history.popitem(last=False)

    FRAUD_SCORE.observe(fraud_score)
    threshold = float(os.getenv("FRAUD_THRESHOLD", "0.75"))
    contributions = {k: round(signals[k] * w, 4) for k, w in SIGNAL_WEIGHTS.items()}
    return {
        "transaction_id": txn.transaction_id,
        "fraud_score": round(fraud_score, 4),
        "is_fraud": fraud_score >= threshold,
        "risk_level": _risk_level(fraud_score),
        "model_version": MODEL_VERSION,
        "signals": signals,
        "contributions": contributions,
        "top_signal": max(contributions, key=lambda k: contributions[k]),
    }


@app.get("/model")
def model() -> dict:
    return {
        "model_version": MODEL_VERSION,
        "weights": SIGNAL_WEIGHTS,
        "threshold": float(os.getenv("FRAUD_THRESHOLD", "0.75")),
    }


def main() -> None:
    run(app, int(os.getenv("PORT", "8091")))


if __name__ == "__main__":
    main()
