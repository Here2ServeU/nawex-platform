# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""healthcare_simulator.py

Generates realistic synthetic healthcare data streams for NAWEX demos.

All data is fully synthetic — no real patient information is used or generated.
Patient identifiers are random tokens compliant with HIPAA Safe Harbor method
(45 CFR §164.514(b)) — no real names, dates of birth, or geographic data finer
than state level.

Used by the NAWEX client portal (live streaming) and demo_client.py (narrated demo).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd


_RNG = np.random.default_rng(seed=42)
_DEPARTMENTS = ["ICU", "Emergency", "Cardiology", "General Med", "Oncology", "Neurology", "Surgery"]
_ROLES = ["clinician", "nurse", "pharmacist", "admin", "it_support", "researcher", "contractor"]
_FHIR_RESOURCE_TYPES = ["Patient", "Observation", "Condition", "MedicationRequest", "Procedure", "DiagnosticReport"]
_ACCESS_TYPES = ["read", "search", "write", "print", "copy", "bulk_export"]


def make_patient_vitals_stream(
    n_patients: int = 24,
    n_timepoints: int = 60,
    inject_anomalies: bool = True,
    anomaly_rate: float = 0.08,
    seed: Optional[int] = 42,
) -> pd.DataFrame:
    """
    Generate a realistic stream of patient vital signs for demo purposes.

    Simulates continuous monitoring of an inpatient unit with normal baselines
    and injected clinical anomalies (SpO2 drops, tachycardia, hypertensive crises).

    Args:
        n_patients: Number of patients being monitored simultaneously
        n_timepoints: Number of monitoring intervals (minutes) per patient
        inject_anomalies: Whether to inject clinical alert events
        anomaly_rate: Fraction of readings to flag as anomalous
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: patient_id, timestamp, heart_rate, spo2,
        systolic_bp, diastolic_bp, temperature, respiratory_rate,
        department, acuity_level, clinical_risk_score, is_alert
    """
    rng = np.random.default_rng(seed)
    rows = []
    base_time = datetime.now() - timedelta(hours=1)

    patient_ids = [f"PT-{rng.integers(10000, 99999)}" for _ in range(n_patients)]
    patient_depts = {pid: rng.choice(_DEPARTMENTS) for pid in patient_ids}
    patient_acuity = {pid: rng.choice([1, 2, 3], p=[0.15, 0.45, 0.40]) for pid in patient_ids}

    for t in range(n_timepoints):
        ts = base_time + timedelta(minutes=t)
        for pid in patient_ids:
            dept = patient_depts[pid]
            acuity = patient_acuity[pid]

            # Baseline vitals with department-appropriate variance
            hr_base = 72 + (acuity - 2) * 10 + rng.normal(0, 8)
            spo2_base = 97 - (acuity - 1) * 0.5 + rng.normal(0, 1)
            sbp_base = 120 + (acuity - 2) * 10 + rng.normal(0, 12)
            dbp_base = 78 + rng.normal(0, 8)
            temp_base = 37.0 + rng.normal(0, 0.3)
            rr_base = 16 + rng.normal(0, 2)

            is_alert = False
            anomaly_type = None

            # Inject clinical anomalies
            if inject_anomalies and rng.random() < anomaly_rate:
                anomaly_scenario = rng.choice([
                    "tachycardia", "spo2_drop", "hypertensive_crisis",
                    "bradycardia", "hypotension", "fever"
                ])
                if anomaly_scenario == "tachycardia":
                    hr_base = rng.uniform(131, 165)
                elif anomaly_scenario == "spo2_drop":
                    spo2_base = rng.uniform(82, 87)
                elif anomaly_scenario == "hypertensive_crisis":
                    sbp_base = rng.uniform(191, 220)
                elif anomaly_scenario == "bradycardia":
                    hr_base = rng.uniform(30, 44)
                elif anomaly_scenario == "hypotension":
                    sbp_base = rng.uniform(60, 79)
                elif anomaly_scenario == "fever":
                    temp_base = rng.uniform(39.6, 41.0)
                is_alert = True
                anomaly_type = anomaly_scenario

            # Composite clinical risk score (weighted vitals deviation)
            hr_risk = min(abs(hr_base - 72) / 60.0, 1.0)
            spo2_risk = max(0, (97 - spo2_base) / 15.0)
            bp_risk = min(abs(sbp_base - 120) / 80.0, 1.0)
            acuity_weight = acuity / 3.0
            clinical_risk = min(
                0.35 * hr_risk + 0.35 * spo2_risk + 0.20 * bp_risk + 0.10 * acuity_weight,
                1.0
            )

            rows.append({
                "patient_id": pid,
                "timestamp": ts,
                "department": dept,
                "acuity_level": acuity,
                "heart_rate": round(float(hr_base), 1),
                "spo2": round(float(np.clip(spo2_base, 70, 100)), 1),
                "systolic_bp": round(float(sbp_base), 0),
                "diastolic_bp": round(float(np.clip(dbp_base, 40, 130)), 0),
                "temperature": round(float(temp_base), 1),
                "respiratory_rate": round(float(np.clip(rr_base, 6, 40)), 0),
                "clinical_risk_score": round(float(clinical_risk), 4),
                "anomaly_type": anomaly_type,
                "is_alert": is_alert,
            })

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def make_phi_access_log(
    n_users: int = 15,
    n_events: int = 200,
    inject_suspicious: bool = True,
    suspicious_rate: float = 0.12,
    seed: Optional[int] = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic PHI access audit log for HIPAA compliance demo.

    Injects realistic suspicious access patterns: bulk exports, after-hours
    contractor access, and cross-department record pulls.

    Args:
        n_users: Number of distinct users accessing EHR
        n_events: Total access events to generate
        inject_suspicious: Whether to inject flagged access events
        suspicious_rate: Fraction of events that are anomalous
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: user_id, role, department, patient_id,
        access_type, record_count, timestamp, is_after_hours, is_weekend,
        cross_department, phi_risk_score, is_flagged
    """
    rng = np.random.default_rng(seed)
    base_time = datetime.now() - timedelta(days=7)

    user_ids = [f"USR-{rng.integers(1000, 9999)}" for _ in range(n_users)]
    user_roles = {uid: rng.choice(_ROLES, p=[0.30, 0.25, 0.10, 0.10, 0.10, 0.08, 0.07]) for uid in user_ids}
    user_depts = {uid: rng.choice(_DEPARTMENTS) for uid in user_ids}

    rows = []
    for _ in range(n_events):
        uid = rng.choice(user_ids)
        role = user_roles[uid]
        user_dept = user_depts[uid]

        # Random timestamp within past 7 days
        offset_seconds = rng.integers(0, 7 * 24 * 3600)
        ts = base_time + timedelta(seconds=int(offset_seconds))
        hour = ts.hour
        is_after_hours = (hour < 7 or hour > 20)
        is_weekend = ts.weekday() >= 5

        # Normal access pattern
        access_type = rng.choice(_ACCESS_TYPES, p=[0.55, 0.20, 0.12, 0.06, 0.05, 0.02])
        record_count = int(rng.integers(1, 5))
        accessed_dept = user_dept
        cross_department = False
        is_flagged = False

        # Inject suspicious events
        if inject_suspicious and rng.random() < suspicious_rate:
            suspicious_scenario = rng.choice([
                "bulk_export_contractor",
                "after_hours_admin",
                "cross_dept_it",
                "mass_access",
            ])
            if suspicious_scenario == "bulk_export_contractor":
                access_type = "bulk_export"
                record_count = int(rng.integers(150, 600))
                role = "contractor"
            elif suspicious_scenario == "after_hours_admin":
                access_type = rng.choice(["print", "copy"])
                ts = ts.replace(hour=rng.integers(1, 5).item())
                is_after_hours = True
                role = "admin"
            elif suspicious_scenario == "cross_dept_it":
                accessed_dept = rng.choice([d for d in _DEPARTMENTS if d != user_dept])
                cross_department = True
                role = "it_support"
            elif suspicious_scenario == "mass_access":
                record_count = int(rng.integers(80, 200))
                access_type = rng.choice(["read", "search"])
            is_flagged = True

        # Simple phi_risk_score proxy
        phi_risk = (
            0.30 * min(record_count / 100.0, 1.0)
            + 0.25 * (0.5 if is_after_hours else 0.0)
            + 0.20 * (1.0 if cross_department else 0.0)
            + 0.15 * {"bulk_export": 0.9, "print": 0.5, "copy": 0.4, "write": 0.2, "read": 0.05, "search": 0.1}.get(access_type, 0.1)
            + 0.10 * {"contractor": 0.8, "it_support": 0.5, "admin": 0.3, "researcher": 0.4,
                      "clinician": 0.05, "nurse": 0.05, "pharmacist": 0.1}.get(role, 0.2)
        )

        rows.append({
            "user_id": uid,
            "role": role,
            "user_department": user_dept,
            "accessed_department": accessed_dept,
            "patient_id": f"PT-{rng.integers(10000, 99999)}",
            "access_type": access_type,
            "record_count": record_count,
            "timestamp": ts,
            "is_after_hours": is_after_hours,
            "is_weekend": is_weekend,
            "cross_department": cross_department,
            "phi_risk_score": round(float(phi_risk), 4),
            "is_flagged": is_flagged,
        })

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def make_ehr_ingestion_stream(
    n_records: int = 500,
    inject_errors: bool = True,
    error_rate: float = 0.04,
    seed: Optional[int] = 42,
) -> pd.DataFrame:
    """
    Generate a synthetic FHIR R4 EHR ingestion stream for demo.

    Simulates real-time FHIR resource ingestion including latency distributions
    and validation error injection.

    Args:
        n_records: Number of FHIR records to simulate
        inject_errors: Whether to inject ingestion errors
        error_rate: Fraction of records with errors
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: record_id, fhir_resource_type, patient_id,
        facility, ingestion_latency_ms, status, error_code, timestamp
    """
    rng = np.random.default_rng(seed)
    base_time = datetime.now() - timedelta(hours=2)
    facilities = ["City Medical Center", "St. Luke's Hospital", "Regional Health System",
                  "University Medical Center", "Children's Hospital"]
    error_codes = ["FHIR_VALIDATION_ERROR", "MISSING_REQUIRED_FIELD", "DUPLICATE_RESOURCE",
                   "ENCODING_ERROR", "TIMEOUT"]

    rows = []
    for i in range(n_records):
        ts = base_time + timedelta(seconds=i * 14)  # ~1 record per 14 seconds
        resource_type = rng.choice(
            _FHIR_RESOURCE_TYPES,
            p=[0.10, 0.35, 0.20, 0.20, 0.10, 0.05]
        )

        # Latency: log-normal distribution centered around 45ms
        latency = float(rng.lognormal(mean=3.8, sigma=0.6))
        latency = float(np.clip(latency, 5, 500))

        status = "success"
        error_code = None

        if inject_errors and rng.random() < error_rate:
            status = "error"
            error_code = rng.choice(error_codes)
            latency = float(rng.uniform(200, 500))

        rows.append({
            "record_id": f"FHIR-{i+1:05d}",
            "fhir_resource_type": resource_type,
            "patient_id": f"PT-{rng.integers(10000, 99999)}",
            "facility": rng.choice(facilities),
            "ingestion_latency_ms": round(latency, 2),
            "status": status,
            "error_code": error_code,
            "timestamp": ts,
        })

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df
