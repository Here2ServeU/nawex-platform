"""EHR ingestion service — FHIR R4 resource intake with HIPAA §164.312(b) audit logging."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
import uuid
from collections import deque

from fastapi import HTTPException, Query
from prometheus_client import Counter
from pydantic import BaseModel, Field

from golden.services.common import ChaosState, chaos_router, create_app, run

SERVICE = "ehr-ingestion"
FHIR_RESOURCE_TYPES = frozenset(
    {
        "Patient",
        "Observation",
        "Condition",
        "Procedure",
        "MedicationRequest",
        "DiagnosticReport",
        "Encounter",
        "AllergyIntolerance",
        "Immunization",
        "CarePlan",
    }
)
EHR_RECORDS = Counter("golden_ehr_records_total", "EHR records ingested.", ["status"])

logger = logging.getLogger(SERVICE)
app = create_app(SERVICE, "FHIR R4 ingestion with PHI access auditing.")
chaos = ChaosState()
app.include_router(chaos_router(chaos))

ehr_records: deque[dict] = deque(maxlen=50_000)
_lock = threading.Lock()


def _pseudonym(patient_id: str) -> str:
    """Stable pseudonymous token so audit logs never contain the raw identifier."""
    return "pt-" + hashlib.sha256(patient_id.encode()).hexdigest()[:12]


class EHRRecordIn(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=128)
    resource_type: str = Field("Observation", max_length=64)
    encounter_id: str | None = Field(None, max_length=128)
    department: str = Field("general", max_length=64)
    data_class: str = Field("clinical", max_length=64)
    phi_flag: bool = True


@app.post("/api/v1/ehr/ingest", status_code=201)
async def ingest(body: EHRRecordIn) -> dict:
    if await chaos.apply():
        EHR_RECORDS.labels(status="error").inc()
        raise HTTPException(status_code=503, detail="injected failure")
    if body.resource_type not in FHIR_RESOURCE_TYPES:
        EHR_RECORDS.labels(status="rejected").inc()
        raise HTTPException(
            status_code=422,
            detail={"reason": "invalid_resource_type", "allowed": sorted(FHIR_RESOURCE_TYPES)},
        )
    record = {
        "id": str(uuid.uuid4()),
        **body.model_dump(),
        "encounter_id": body.encounter_id or str(uuid.uuid4()),
        "status": "accepted",
        "timestamp": time.time(),
    }
    if body.phi_flag:
        logger.info(
            "hipaa_audit",
            extra={
                "event": "phi_ingest",
                "record": record["id"],
                "subject": _pseudonym(body.patient_id),
                "resource": body.resource_type,
                "actor": "system",
            },
        )
    with _lock:
        ehr_records.append(record)
    EHR_RECORDS.labels(status="accepted").inc()
    return record


@app.get("/api/v1/ehr/records")
def list_records(limit: int = Query(50, ge=1, le=500), department: str | None = None) -> dict:
    with _lock:
        items = [r for r in ehr_records if department is None or r["department"] == department]
    return {"records": items[-limit:], "total": len(items)}


@app.get("/api/v1/ehr/patient/{patient_id}")
def patient_records(patient_id: str) -> dict:
    logger.info(
        "hipaa_audit", extra={"event": "phi_read", "subject": _pseudonym(patient_id), "actor": "system"}
    )
    with _lock:
        items = [r for r in ehr_records if r["patient_id"] == patient_id]
    return {"patient_id": patient_id, "records": items, "total": len(items)}


def main() -> None:
    run(app, int(os.getenv("PORT", "8093")))


if __name__ == "__main__":
    main()
