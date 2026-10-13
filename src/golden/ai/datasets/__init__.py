"""Synthetic datasets for demos and tests (healthcare, fintech, SLI telemetry)."""

from .fintech_simulator import (
    make_fraud_scenario_stream,
    make_payment_latency_stream,
    make_settlement_batch_stream,
)
from .healthcare_simulator import make_ehr_ingestion_stream, make_patient_vitals_stream, make_phi_access_log
from .sample_data import make_sli_dataset, make_transactions_dataset

__all__ = [
    "make_ehr_ingestion_stream",
    "make_fraud_scenario_stream",
    "make_patient_vitals_stream",
    "make_payment_latency_stream",
    "make_phi_access_log",
    "make_settlement_batch_stream",
    "make_sli_dataset",
    "make_transactions_dataset",
]
