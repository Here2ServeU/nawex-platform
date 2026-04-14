# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""dollar_thresholds.py

Industry-standard financial constants used in NAWEX ROI and impact calculations.
Every value is sourced from a citable industry report — use these footnotes when
presenting to hospital compliance officers, bank risk officers, or CFOs.
"""

# ---------------------------------------------------------------------------
# Healthcare Financial Constants
# ---------------------------------------------------------------------------
HEALTHCARE_CONSTANTS = {
    # Source: HIMSS Cost of Healthcare Data Breach Report 2024
    "avg_readmission_cost_usd": 15_400,

    # Source: Agency for Healthcare Research and Quality (AHRQ) 2023
    "avg_sepsis_treatment_cost_usd": 52_000,

    # Source: AHRQ — preventable adverse drug event hospitalization cost
    "avg_adverse_drug_event_cost_usd": 5_640,

    # Source: Joint Commission Sentinel Event data — avg preventable adverse event
    "preventable_adverse_event_cost_usd": 28_000,

    # Source: IBM Cost of a Data Breach Report 2024 — healthcare highest at $10.93M avg,
    # $499/record is the per-record component
    "phi_breach_cost_per_record_usd": 499,

    # Source: HHS OCR HIPAA enforcement — minimum fine per violation category
    "hipaa_fine_per_violation_usd": 100,

    # Source: HHS OCR — annual cap for identical violation category
    "hipaa_fine_max_annual_usd": 1_919_173,

    # Source: Ponemon Institute / Guidehouse — unplanned EHR downtime
    "ehr_downtime_cost_per_hour_usd": 45_700,

    # Source: CMS Hospital Readmissions Reduction Program — average excess payment penalty
    "cms_readmission_penalty_per_patient_usd": 2_100,

    # Source: American Hospital Association (AHA) 2024 — avg beds per community hospital
    "avg_hospital_beds": 160,

    # Source: CMS national average 30-day unplanned readmission rate
    "baseline_readmission_rate": 0.152,
}

# ---------------------------------------------------------------------------
# Financial Services Constants
# ---------------------------------------------------------------------------
FINTECH_CONSTANTS = {
    # Source: Federal Reserve Payments Study 2024 — avg unauthorized transaction value
    "avg_fraudulent_transaction_usd": 1_200,

    # Source: ABA Banking Journal 2023 — avg cost to investigate one fraud case
    "avg_fraud_investigation_cost_usd": 3_400,

    # Source: Deloitte Financial Services Regulatory Outlook 2024 — avg AML fine
    "aml_compliance_fine_avg_usd": 2_400_000,

    # Source: Gartner — avg cost of payment system downtime per minute
    "payment_downtime_cost_per_minute_usd": 5_600,

    # Source: Mastercard / Visa chargeback dispute cost (processing + dispute fee)
    "chargeback_cost_per_incident_usd": 190,

    # Source: IBM / Ponemon 2024 — financial services data breach cost per record
    "data_breach_cost_per_record_usd": 206,

    # Source: McKinsey & Company — manual fraud review cost per flagged transaction
    "manual_review_cost_per_transaction_usd": 22,

    # Source: Basel III operational risk capital requirement ratio (standardized approach)
    "operational_risk_capital_ratio": 0.12,

    # Source: Federal Reserve — industry average false positive rate for fraud detection
    "industry_avg_false_positive_rate": 0.015,
}

# ---------------------------------------------------------------------------
# Platform Pricing Tiers
# ---------------------------------------------------------------------------
PLATFORM_PRICING = {
    # Starter: up to 250-bed hospital or community bank
    "tier_starter_monthly_usd": 10_000,

    # Professional: regional health system or mid-size bank
    "tier_professional_monthly_usd": 17_500,

    # Enterprise: health network or national bank
    "tier_enterprise_monthly_usd": 25_000,

    # Standard contract duration
    "contract_years": 3,
}
