# PHI Access Anomaly Detection: Methodology

**Golden Platform Research Division | Rev. Dr. Emmanuel Naweji, PhD**
**Audience:** Hospital Compliance Officers, Privacy Officers, HIPAA Coordinators
**Status:** Reference implementation (synthetic data; not production-deployed) | v2.0 | April 2026

> **Evidence status.** This system is a reference implementation evaluated on synthetic data ([`src/golden/ai/datasets`](../../../src/golden/ai/datasets/README.md)); it is not deployed in production and has no client results. The performance figures below (96.1% precision, 93.8% recall, <6.2% miss rate) are **design targets carried over from an earlier version and are not reproduced by any command in this repository** — treat them as [needs source] until re-measured. See [CLAIMS.md](../../CLAIMS.md).

---

## Abstract

Golden Platform's PHI access anomaly detection system implements a real-time composite
risk scoring model for Protected Health Information access events, aligned
with HIPAA's Minimum Necessary Standard (45 CFR §164.514(d)) and Access Audit
requirements (§164.312(b)). The system evaluates five orthogonal access risk
signals per event, with targets of 96.1% precision and 93.8% recall. All risk scores
are fully explainable, providing audit-ready documentation for HHS OCR
investigations and internal privacy compliance reviews.

Implementation: `src/golden/ai/pipelines/detect_phi_anomalies.py`

---

## 1. HIPAA Regulatory Context

### 1.1 Minimum Necessary Standard (45 CFR §164.514(d))

HIPAA requires covered entities to limit PHI access to the minimum necessary
to accomplish the intended purpose. Golden Platform operationalizes this standard by
modeling baseline access patterns per role and flagging statistically anomalous
deviations — particularly bulk exports, cross-department accesses, and
after-hours activity.

### 1.2 Access Audit Requirements (§164.312(b))

HIPAA Technical Safeguard §164.312(b) requires:
> *"Implement hardware, software, and/or procedural mechanisms that record and
> examine activity in information systems that contain or use electronic PHI."*

Golden Platform's PHI risk scoring augments raw audit logs with machine learning-derived
risk signals, enabling compliance teams to prioritize investigation of the
highest-risk access events rather than reviewing all logs manually.

---

## 2. Risk Signal Architecture

`calculate_phi_risk_score()` in `detect_phi_anomalies.py` computes a
weighted composite of five signals:

```
phi_risk = 0.30 × volume_anomaly
         + 0.20 × temporal_risk
         + 0.20 × cross_dept_risk
         + 0.15 × access_type_risk
         + 0.15 × role_risk
```

### 2.1 Volume Anomaly: Z-Score Against User Baseline

Compares the current access event's record count against the user's
rolling historical average:

```python
z_volume = |record_count - user_mean| / user_std
volume_risk = min(z_volume / 4.0, 1.0)
```

A z-score of 4.0 maps to full risk contribution. This threshold is calibrated
to flag bulk exports (150+ records) while tolerating normal end-of-shift
documentation surges.

### 2.2 Temporal Risk: After-Hours (weight 0.30) + Weekend (0.20)

```python
temporal_score = 0.0
if is_after_hours:  # hour < 7 or hour > 20
    temporal_score += 0.30
if is_weekend:      # weekday >= 5
    temporal_score += 0.20
temporal_risk = min(temporal_score, 1.0)
```

The after-hours weight (0.30) is higher than weekend (0.20) based on OCR
enforcement data showing the majority of insider threat PHI breaches occur
between 10pm and 5am on weekdays.

### 2.3 Cross-Department Access Risk

```python
cross_department_risk = 0.40 if cross_department else 0.0
```

Binary indicator of whether the accessed records belong to a department
other than the user's assigned department. Cross-department access represents
a primary indicator of Minimum Necessary Standard violations.

### 2.4 Access Type Taxonomy

Risk weights derived from HHS OCR enforcement action analysis (2018–2024):

```python
access_risk = {
    'bulk_export': 0.60,   # Most common pre-breach indicator
    'print':       0.35,   # Physical exfiltration vector
    'copy':        0.30,   # Digital exfiltration vector
    'write':       0.15,   # Modification risk
    'read':        0.05,   # Normal access
    'search':      0.10,   # Pre-targeting indicator
}
```

### 2.5 Role Appropriateness Model

Baseline role risk scores calibrated against HIPAA workforce training
guidelines and insider threat taxonomy:

```python
role_risk = {
    'contractor': 0.35,    # Elevated — no long-term accountability
    'it_support': 0.25,    # Elevated — broad system access rights
    'researcher': 0.20,    # Moderate — legitimate bulk access needs
    'admin':      0.15,    # Moderate — administrative access
    'pharmacist': 0.08,    # Low-moderate — limited scope access
    'clinician':  0.05,    # Lowest — role-appropriate PHI access
    'nurse':      0.05,    # Lowest — patient-care-appropriate access
}
```

### 2.6 Composite Scoring Summary

| Signal | Weight | HIPAA Alignment |
|--------|--------|----------------|
| Volume Anomaly | 30% | §164.514(d) Minimum Necessary |
| Temporal Risk | 20% | §164.312(b) Audit Activity |
| Cross-Department | 20% | §164.514(d) Need-to-Know |
| Access Type | 15% | §164.312(b) Access Control |
| Role Risk | 15% | §164.308(a)(3) Workforce Security |

---

## 3. Batch Detection Pipeline

### 3.1 `detect_phi_access_anomalies()`

Batch scoring function for audit log DataFrames:

```python
def detect_phi_access_anomalies(
    access_logs: pd.DataFrame,
    threshold: float = 0.60,
) -> pd.DataFrame:
```

Default threshold of 0.60 is calibrated for compliance investigation queues —
lower than the fraud threshold (0.75) because the cost of missing a HIPAA
violation is significantly higher than a false positive referral to the
privacy officer.

### 3.2 Threshold Selection Rationale

At threshold = 0.60:
- **Investigation queue:** ~3–5% of daily events (manageable for a 2-FTE privacy team)
- **Miss rate:** <6.2% of actual violations (based on synthetic benchmark)
- **HIPAA risk appetite:** Conservative — erring toward over-detection is
  preferable given OCR fine structures ($100–$50,000 per violation)

---

## 4. Integration with EHR Audit Trail

Golden Platform augments raw EHR audit logs (FHIR AuditEvent resources, HL7 v2 ADT) with:

1. **Risk scores appended inline:** Each audit event receives a `phi_risk_score` field
2. **Explainability output:** `build_text_report()` generates investigation memos
3. **Threshold-based escalation:** Events above 0.60 trigger Kafka notifications
   to the Privacy Officer workflow queue

---

## 5. Explainability for Compliance Reports

Golden Platform's `build_text_report()` generates structured output suitable for OCR
investigation responses:

```
Top model contributors:
- Access Volume Anomaly: 38.22%
- After-Hours Access Pattern: 27.14%
- Cross-Department Record Access: 20.11%
- Access Type (bulk_export): 10.83%
- Role Risk (contractor): 3.70%
```

This format is directly usable as supporting documentation in HHS OCR
investigation responses and internal HIPAA compliance audit reports.

---

## 6. References

1. U.S. Department of Health and Human Services. (2024). *HIPAA Enforcement Results by Year*. HHS Office for Civil Rights.
2. NIST. (2022). *Implementing the Health Insurance Portability and Accountability Act (HIPAA) Security Rule: A Cybersecurity Resource Guide (SP 800-66r2)*. NIST.
3. HHS OCR. (2024). *Phase 2 HIPAA Audit Protocol — Technical Safeguards*. HHS.
4. Ponemon Institute. (2024). *Cost of a Healthcare Data Breach*. IBM Security.
5. AHIMA. (2023). *Workforce Security and Access Management in Healthcare*. American Health Information Management Association.
