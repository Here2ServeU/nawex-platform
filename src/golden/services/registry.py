"""Service catalog: name → (ASGI app import path, default port). Single source of truth for the CLI."""

from __future__ import annotations

SERVICES: dict[str, tuple[str, int]] = {
    "api": ("golden.api.app:app", 8000),
    "transaction-engine": ("golden.services.fintech.transaction_engine:app", 8090),
    "fraud-detector": ("golden.services.fintech.fraud_detector:app", 8091),
    "payment-gateway": ("golden.services.fintech.payment_gateway:app", 8092),
    "ehr-ingestion": ("golden.services.healthcare.ehr_ingestion:app", 8093),
    "clinical-decision": ("golden.services.healthcare.clinical_decision:app", 8094),
    "patient-gateway": ("golden.services.healthcare.patient_gateway:app", 8095),
    "gpu-optimizer": ("golden.services.gpu.optimizer:app", 8096),
    "migration-planner": ("golden.services.migration.planner:app", 8097),
    "identity-governance": ("golden.services.identity.governance:app", 8098),
}
