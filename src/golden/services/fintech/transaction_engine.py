"""Transaction engine — validates, risk-checks and records payment transactions."""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections import deque

from fastapi import HTTPException, Query
from prometheus_client import Counter
from pydantic import BaseModel, Field

from golden.ai.pipelines.detect_fraud import calculate_fraud_score
from golden.security.guardrails import clamp_score
from golden.services.common import ChaosState, chaos_router, create_app, run

SERVICE = "transaction-engine"
TRANSACTIONS = Counter("golden_transactions_total", "Transactions processed.", ["status"])

app = create_app(SERVICE, "Payment transaction intake with inline fraud gating.")
chaos = ChaosState()
app.include_router(chaos_router(chaos))

transactions: deque[dict] = deque(maxlen=10_000)
_lock = threading.Lock()


class TransactionIn(BaseModel):
    account_id: str = Field(..., max_length=128)
    amount: float = Field(..., gt=0, le=10_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    merchant: str = Field("unknown", max_length=256)
    merchant_category_code: str = Field("0000", max_length=4)
    channel: str = Field("online", max_length=32)
    country_code: str = Field("US", min_length=2, max_length=2)
    fraud_score: float | None = Field(
        None, ge=0, le=1, description="Pre-computed score; scored inline if absent."
    )


@app.post("/api/v1/transactions", status_code=201)
async def process_transaction(body: TransactionIn) -> dict:
    started = time.perf_counter()
    if await chaos.apply():
        TRANSACTIONS.labels(status="error").inc()
        raise HTTPException(status_code=503, detail="injected failure")

    score = body.fraud_score if body.fraud_score is not None else calculate_fraud_score(body.model_dump())
    score = clamp_score(score)
    threshold = float(os.getenv("BLOCK_THRESHOLD", "0.85"))
    txn = {
        "id": str(uuid.uuid4()),
        **body.model_dump(exclude={"fraud_score"}),
        "fraud_score": round(score, 4),
        "status": "blocked" if score > threshold else "approved",
        "timestamp": time.time(),
    }
    if txn["status"] == "blocked":
        txn["reason"] = "fraud_score_exceeded"
    txn["processing_ms"] = round((time.perf_counter() - started) * 1000, 2)
    with _lock:
        transactions.append(txn)
    TRANSACTIONS.labels(status=txn["status"]).inc()
    return txn


@app.get("/api/v1/transactions")
def list_transactions(limit: int = Query(50, ge=1, le=500)) -> dict:
    with _lock:
        items = list(transactions)
    return {"transactions": items[-limit:], "total": len(items)}


@app.get("/api/v1/settlement/status")
def settlement_status() -> dict:
    with _lock:
        count = len(transactions)
        approved = sum(1 for t in transactions if t["status"] == "approved")
    return {"status": "open", "transactions_processed": count, "approved": approved}


def main() -> None:
    run(app, int(os.getenv("PORT", "8090")))


if __name__ == "__main__":
    main()
