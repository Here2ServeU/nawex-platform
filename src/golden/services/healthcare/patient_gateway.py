"""Patient data gateway — FHIR query facade with consent enforcement (HIPAA §164.508)."""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from collections import deque

from fastapi import HTTPException
from pydantic import BaseModel, Field

from golden.services.common import ChaosState, chaos_router, create_app, run

SERVICE = "patient-gateway"
app = create_app(SERVICE, "FHIR R4 / HL7 v2 gateway with consent verification.")
chaos = ChaosState()
app.include_router(chaos_router(chaos))

consents: deque[dict] = deque(maxlen=100_000)
queries: deque[dict] = deque(maxlen=10_000)
_lock = threading.Lock()


class FHIRQuery(BaseModel):
    patient_id: str = Field(..., max_length=128)
    resource_type: str = Field("Patient", max_length=64)
    scope: str = Field("treatment", max_length=32)
    format: str = Field("FHIR-R4", max_length=16)


class ConsentIn(BaseModel):
    patient_id: str = Field(..., max_length=128)
    scope: str = Field("treatment", max_length=32)
    granted_to: str = Field("primary-care-provider", max_length=128)
    valid_days: int = Field(365, ge=1, le=3650)


def _has_consent(patient_id: str, scope: str) -> bool:
    now = time.time()
    with _lock:
        return any(
            c["patient_id"] == patient_id and c["scope"] == scope and c["valid_until"] > now for c in consents
        )


@app.post("/api/v1/fhir/query")
async def fhir_query(q: FHIRQuery) -> dict:
    if await chaos.apply():
        raise HTTPException(status_code=502, detail="GATEWAY_ERROR: simulated FHIR failure")
    if os.getenv("CONSENT_VERIFICATION", "true").lower() == "true" and not _has_consent(
        q.patient_id, q.scope
    ):
        raise HTTPException(status_code=403, detail="no active consent for this scope")
    result = {
        "request_id": str(uuid.uuid4()),
        "patient_id": q.patient_id,
        "resource_type": q.resource_type,
        "status": "completed",
        "result_count": int(hashlib.sha256(q.patient_id.encode()).hexdigest(), 16) % 15 + 1,
        "format": q.format,
    }
    with _lock:
        queries.append(result)
    return result


@app.post("/api/v1/consent/register", status_code=201)
def register_consent(c: ConsentIn) -> dict:
    consent = {
        "consent_id": str(uuid.uuid4()),
        **c.model_dump(),
        "status": "active",
        "valid_until": time.time() + c.valid_days * 86_400,
    }
    with _lock:
        consents.append(consent)
    return consent


@app.post("/api/v1/consent/verify")
def verify_consent(q: FHIRQuery) -> dict:
    return {
        "patient_id": q.patient_id,
        "scope": q.scope,
        "consent_granted": _has_consent(q.patient_id, q.scope),
    }


def main() -> None:
    run(app, int(os.getenv("PORT", "8095")))


if __name__ == "__main__":
    main()
