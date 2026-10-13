"""Payment gateway simulator — processor interactions, settlement batches and fault injection."""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections import deque

from fastapi import HTTPException
from pydantic import BaseModel, Field

from golden.services.common import ChaosState, chaos_router, create_app, run

SERVICE = "payment-gateway"
app = create_app(SERVICE, "Simulated payment processor with settlement batching.")
chaos = ChaosState()
app.include_router(chaos_router(chaos))

payments: deque[dict] = deque(maxlen=10_000)
batches: deque[dict] = deque(maxlen=1_000)
_lock = threading.Lock()


class PaymentIn(BaseModel):
    transaction_id: str | None = Field(None, max_length=128)
    amount: float = Field(..., gt=0, le=10_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)


@app.post("/api/v1/process", status_code=201)
async def process_payment(body: PaymentIn) -> dict:
    started = time.perf_counter()
    if await chaos.apply():
        raise HTTPException(status_code=502, detail="GATEWAY_ERROR: simulated processor failure")
    payment = {
        "payment_id": str(uuid.uuid4()),
        "transaction_id": body.transaction_id or str(uuid.uuid4()),
        "amount": body.amount,
        "currency": body.currency,
        "status": "settled",
        "processor_response_code": "00",
        "timestamp": time.time(),
        "processing_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    with _lock:
        payments.append(payment)
    return payment


@app.post("/api/v1/settlement/trigger", status_code=201)
def trigger_settlement() -> dict:
    with _lock:
        batch = {
            "batch_id": str(uuid.uuid4()),
            "status": "processing",
            "transactions_count": len(payments),
            "total_amount": round(sum(p["amount"] for p in payments), 2),
            "started_at": time.time(),
        }
        batches.append(batch)
    return batch


@app.get("/api/v1/settlement/batches")
def list_batches() -> dict:
    with _lock:
        return {"batches": list(batches), "total": len(batches)}


def main() -> None:
    run(app, int(os.getenv("PORT", "8092")))


if __name__ == "__main__":
    main()
