# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""roi_calculator.py

Aggregate ROI model for NAWEX platform consulting engagements.

Produces a single ROI summary object that answers the C-suite question:
"What do I get for $10,000–$25,000 per month?"

For hospital CIOs:
    Monthly contract cost vs. monthly readmission, breach, and downtime exposure.

For bank risk officers:
    Monthly contract cost vs. monthly fraud loss, compliance, and downtime exposure.
"""

from __future__ import annotations

import json
from typing import Dict, Any, Optional

from .dollar_thresholds import PLATFORM_PRICING
from .impact_estimator import ImpactEstimator


class ROICalculator:
    """
    Aggregates NAWEX AI impact estimates into a complete ROI justification.

    Usage:
        calc = ROICalculator(vertical="healthcare", tier="professional")
        roi = calc.compute_hospital_roi(patients_per_day=450,
                                        phi_records_total=250_000,
                                        ehr_queries_per_hour=2_000)
        print(roi["executive_summary"])
        print(f"ROI multiple: {roi['roi_ratio']:.1f}x")
    """

    def __init__(self, vertical: str = "healthcare", tier: str = "professional") -> None:
        if vertical not in ("healthcare", "fintech"):
            raise ValueError("vertical must be 'healthcare' or 'fintech'")
        if tier not in ("starter", "professional", "enterprise"):
            raise ValueError("tier must be 'starter', 'professional', or 'enterprise'")
        self.vertical = vertical
        self.tier = tier
        self.monthly_cost = PLATFORM_PRICING[f"tier_{tier}_monthly_usd"]
        self.estimator = ImpactEstimator(vertical)
        self._last_result: Optional[Dict[str, Any]] = None

    def compute_hospital_roi(
        self,
        patients_per_day: int = 450,
        phi_records_total: int = 250_000,
        ehr_queries_per_hour: int = 2_000,
        clinical_risk_score: float = 0.65,
        phi_risk_score: float = 0.45,
        latency_risk_score: float = 0.30,
    ) -> Dict[str, Any]:
        """
        Compute full ROI for a hospital consulting engagement.

        Args:
            patients_per_day: Average daily patient census monitored by NAWEX
            phi_records_total: Total PHI records in scope
            ehr_queries_per_hour: EHR system query throughput
            clinical_risk_score: Composite clinical AI risk score (0–1)
            phi_risk_score: PHI access anomaly risk score (0–1)
            latency_risk_score: EHR latency risk score (0–1)

        Returns:
            Dict with monthly/annual ROI, breakdown, and CIO-ready narrative.
        """
        readmission = self.estimator.estimate_readmission_impact(
            clinical_risk_score=clinical_risk_score,
            patients_monitored_per_day=patients_per_day,
        )
        phi_breach = self.estimator.estimate_phi_breach_impact(
            phi_risk_score=phi_risk_score,
            records_at_risk=phi_records_total,
        )
        downtime = self.estimator.estimate_clinical_downtime_impact(
            latency_risk_score=latency_risk_score,
            ehr_queries_per_hour=ehr_queries_per_hour,
        )

        annual_value = (
            readmission["annual_cost_prevented_usd"]
            + phi_breach["total_exposure_avoided_usd"]
            + downtime["total_avoided_usd"]
        )
        monthly_value = annual_value / 12

        roi_ratio = monthly_value / self.monthly_cost
        payback_days = (self.monthly_cost / monthly_value) * 30 if monthly_value > 0 else 999

        result = {
            "vertical": "healthcare",
            "tier": self.tier,
            "monthly_cost_usd": self.monthly_cost,
            "monthly_value_protected_usd": round(monthly_value, 2),
            "annual_value_protected_usd": round(annual_value, 2),
            "roi_ratio": round(roi_ratio, 1),
            "payback_days": round(payback_days, 1),
            "annual_net_benefit_usd": round(annual_value - (self.monthly_cost * 12), 2),
            "breakdown": {
                "readmission_prevention": {
                    "annual_usd": readmission["annual_cost_prevented_usd"],
                    "label": "30-Day Readmission Prevention",
                    "pct_of_total": round(
                        readmission["annual_cost_prevented_usd"] / annual_value * 100, 1
                    ) if annual_value > 0 else 0,
                },
                "phi_breach_avoidance": {
                    "annual_usd": phi_breach["total_exposure_avoided_usd"],
                    "label": "PHI Breach & HIPAA Exposure",
                    "pct_of_total": round(
                        phi_breach["total_exposure_avoided_usd"] / annual_value * 100, 1
                    ) if annual_value > 0 else 0,
                },
                "ehr_downtime_reduction": {
                    "annual_usd": downtime["total_avoided_usd"],
                    "label": "EHR Downtime & Workflow Loss",
                    "pct_of_total": round(
                        downtime["total_avoided_usd"] / annual_value * 100, 1
                    ) if annual_value > 0 else 0,
                },
            },
            "executive_summary": (
                f"NAWEX generates {roi_ratio:.0f}x ROI for your organization, protecting "
                f"{self.estimator._format_usd(monthly_value)}/month in risk exposure "
                f"on a {self.estimator._format_usd(self.monthly_cost)}/month contract. "
                f"The platform pays for itself in {payback_days:.0f} days through readmission "
                f"prevention, PHI breach avoidance, and EHR reliability — with "
                f"{self.estimator._format_usd(annual_value - self.monthly_cost * 12)} "
                f"in net annual benefit."
            ),
            "details": {
                "readmission": readmission,
                "phi_breach": phi_breach,
                "downtime": downtime,
            },
        }
        self._last_result = result
        return result

    def compute_bank_roi(
        self,
        transactions_per_day: int = 8_000,
        avg_transaction_value: float = 850.0,
        payment_gateways: int = 3,
        fraud_score: float = 0.62,
        latency_risk_score: float = 0.28,
        compliance_risk_score: float = 0.40,
        annual_transaction_volume_usd: float = 68_000_000,
    ) -> Dict[str, Any]:
        """
        Compute full ROI for a financial institution consulting engagement.

        Args:
            transactions_per_day: Daily payment transaction volume
            avg_transaction_value: Average transaction amount in USD
            payment_gateways: Number of payment gateways monitored
            fraud_score: Composite fraud risk score (0–1)
            latency_risk_score: Payment latency risk score (0–1)
            compliance_risk_score: AML/BSA compliance risk score (0–1)
            annual_transaction_volume_usd: Total annual transaction volume in USD

        Returns:
            Dict with monthly/annual ROI, breakdown, and risk officer narrative.
        """
        fraud = self.estimator.estimate_fraud_impact(
            fraud_score=fraud_score,
            transaction_amount=avg_transaction_value,
            transactions_per_day=transactions_per_day,
        )
        downtime = self.estimator.estimate_payment_downtime_impact(
            latency_risk_score=latency_risk_score,
            transactions_per_minute=transactions_per_day // 1440,
            avg_transaction_value=avg_transaction_value,
        )
        compliance = self.estimator.estimate_compliance_impact(
            compliance_risk_score=compliance_risk_score,
            annual_transaction_volume_usd=annual_transaction_volume_usd,
        )

        annual_value = (
            fraud["net_annual_value_usd"]
            + downtime["total_avoided_usd"] * 12  # monthly to annual
            + compliance["total_compliance_value_usd"]
        )
        monthly_value = annual_value / 12

        roi_ratio = monthly_value / self.monthly_cost
        payback_days = (self.monthly_cost / monthly_value) * 30 if monthly_value > 0 else 999

        result = {
            "vertical": "fintech",
            "tier": self.tier,
            "monthly_cost_usd": self.monthly_cost,
            "monthly_value_protected_usd": round(monthly_value, 2),
            "annual_value_protected_usd": round(annual_value, 2),
            "roi_ratio": round(roi_ratio, 1),
            "payback_days": round(payback_days, 1),
            "annual_net_benefit_usd": round(annual_value - (self.monthly_cost * 12), 2),
            "breakdown": {
                "fraud_prevention": {
                    "annual_usd": fraud["net_annual_value_usd"],
                    "label": "Fraud Loss Prevention (Net)",
                    "pct_of_total": round(
                        fraud["net_annual_value_usd"] / annual_value * 100, 1
                    ) if annual_value > 0 else 0,
                },
                "payment_reliability": {
                    "annual_usd": downtime["total_avoided_usd"] * 12,
                    "label": "Payment Downtime & SLO Breaches",
                    "pct_of_total": round(
                        downtime["total_avoided_usd"] * 12 / annual_value * 100, 1
                    ) if annual_value > 0 else 0,
                },
                "compliance_automation": {
                    "annual_usd": compliance["total_compliance_value_usd"],
                    "label": "AML/BSA Compliance Automation",
                    "pct_of_total": round(
                        compliance["total_compliance_value_usd"] / annual_value * 100, 1
                    ) if annual_value > 0 else 0,
                },
            },
            "executive_summary": (
                f"NAWEX generates {roi_ratio:.0f}x ROI for your institution, protecting "
                f"{self.estimator._format_usd(monthly_value)}/month in fraud, downtime, "
                f"and compliance exposure on a {self.estimator._format_usd(self.monthly_cost)}/month contract. "
                f"The platform recovers its cost in {payback_days:.0f} days, with "
                f"{self.estimator._format_usd(annual_value - self.monthly_cost * 12)} "
                f"in net annual benefit."
            ),
            "details": {
                "fraud": fraud,
                "downtime": downtime,
                "compliance": compliance,
            },
        }
        self._last_result = result
        return result

    def to_json(self) -> str:
        """Serialize the last computed ROI result to JSON."""
        if self._last_result is None:
            return json.dumps({"error": "No ROI computed yet. Call compute_hospital_roi() or compute_bank_roi() first."})
        return json.dumps(self._last_result, indent=2)

    @classmethod
    def quick_summary(cls, vertical: str, tier: str = "professional", **kwargs) -> Dict[str, Any]:
        """Convenience method: compute and return ROI in one call."""
        calc = cls(vertical=vertical, tier=tier)
        if vertical == "healthcare":
            return calc.compute_hospital_roi(**kwargs)
        else:
            return calc.compute_bank_roi(**kwargs)
