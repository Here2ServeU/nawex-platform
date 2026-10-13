# ===========================================================================
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""roi_calculator.py

Aggregate ROI model for platform consulting engagements.

Produces a single ROI summary object that answers the C-suite question:
"What do I get for $10,000–$25,000 per month?"

For hospital CIOs:
    Monthly contract cost vs. monthly readmission, breach, and downtime exposure.

For bank risk officers:
    Monthly contract cost vs. monthly fraud loss, compliance, and downtime exposure.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .dollar_thresholds import PLATFORM_PRICING
from .impact_estimator import VERTICALS, ImpactEstimator


class ROICalculator:
    """
    Aggregates AI impact estimates into a complete ROI justification.

    Usage:
        calc = ROICalculator(vertical="healthcare", tier="professional")
        roi = calc.compute_hospital_roi(patients_per_day=450,
                                        phi_records_total=250_000,
                                        ehr_queries_per_hour=2_000)
        print(roi["executive_summary"])
        print(f"ROI multiple: {roi['roi_ratio']:.1f}x")
    """

    def __init__(self, vertical: str = "healthcare", tier: str = "professional") -> None:
        if vertical not in VERTICALS:
            raise ValueError(f"vertical must be one of {VERTICALS}")
        if tier not in ("starter", "professional", "enterprise"):
            raise ValueError("tier must be 'starter', 'professional', or 'enterprise'")
        self.vertical = vertical
        self.tier = tier
        self.monthly_cost = PLATFORM_PRICING[f"tier_{tier}_monthly_usd"]
        self.estimator = ImpactEstimator(vertical)
        self._last_result: dict[str, Any] | None = None

    def compute_hospital_roi(
        self,
        patients_per_day: int = 450,
        phi_records_total: int = 250_000,
        ehr_queries_per_hour: int = 2_000,
        clinical_risk_score: float = 0.65,
        phi_risk_score: float = 0.45,
        latency_risk_score: float = 0.30,
    ) -> dict[str, Any]:
        """
        Compute full ROI for a hospital consulting engagement.

        Args:
            patients_per_day: Average daily patient census monitored by the platform
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
                    "pct_of_total": round(readmission["annual_cost_prevented_usd"] / annual_value * 100, 1)
                    if annual_value > 0
                    else 0,
                },
                "phi_breach_avoidance": {
                    "annual_usd": phi_breach["total_exposure_avoided_usd"],
                    "label": "PHI Breach & HIPAA Exposure",
                    "pct_of_total": round(phi_breach["total_exposure_avoided_usd"] / annual_value * 100, 1)
                    if annual_value > 0
                    else 0,
                },
                "ehr_downtime_reduction": {
                    "annual_usd": downtime["total_avoided_usd"],
                    "label": "EHR Downtime & Workflow Loss",
                    "pct_of_total": round(downtime["total_avoided_usd"] / annual_value * 100, 1)
                    if annual_value > 0
                    else 0,
                },
            },
            "executive_summary": (
                f"Modelled: about {roi_ratio:.0f}x ROI for your organization, protecting "
                f"{self.estimator._format_usd(monthly_value)}/month in risk exposure "
                f"on a {self.estimator._format_usd(self.monthly_cost)}/month contract. "
                f"Payback in about {payback_days:.0f} days through readmission "
                f"prevention, PHI breach avoidance, and EHR reliability — with "
                f"{self.estimator._format_usd(annual_value - self.monthly_cost * 12)} "
                f"in net annual benefit."
                f" (A modelled estimate based on stated assumptions, not a measured result: model performance and loss "
                f"benchmarks are inputs; swap in your own measurements and sourced benchmarks.)"
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
    ) -> dict[str, Any]:
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
                    "pct_of_total": round(fraud["net_annual_value_usd"] / annual_value * 100, 1)
                    if annual_value > 0
                    else 0,
                },
                "payment_reliability": {
                    "annual_usd": downtime["total_avoided_usd"] * 12,
                    "label": "Payment Downtime & SLO Breaches",
                    "pct_of_total": round(downtime["total_avoided_usd"] * 12 / annual_value * 100, 1)
                    if annual_value > 0
                    else 0,
                },
                "compliance_automation": {
                    "annual_usd": compliance["total_compliance_value_usd"],
                    "label": "AML/BSA Compliance Automation",
                    "pct_of_total": round(compliance["total_compliance_value_usd"] / annual_value * 100, 1)
                    if annual_value > 0
                    else 0,
                },
            },
            "executive_summary": (
                f"Modelled: about {roi_ratio:.0f}x ROI for your institution, protecting "
                f"{self.estimator._format_usd(monthly_value)}/month in fraud, downtime, "
                f"and compliance exposure on a {self.estimator._format_usd(self.monthly_cost)}/month contract. "
                f"Payback in about {payback_days:.0f} days, with "
                f"{self.estimator._format_usd(annual_value - self.monthly_cost * 12)} "
                f"in net annual benefit."
                f" (A modelled estimate based on stated assumptions, not a measured result: model performance and loss "
                f"benchmarks are inputs; swap in your own measurements and sourced benchmarks.)"
            ),
            "details": {
                "fraud": fraud,
                "downtime": downtime,
                "compliance": compliance,
            },
        }
        self._last_result = result
        return result

    def _summarize(
        self, vertical: str, annual_value: float, breakdown: dict, details: dict, pitch: str
    ) -> dict[str, Any]:
        monthly_value = annual_value / 12
        roi_ratio = monthly_value / self.monthly_cost
        payback_days = (self.monthly_cost / monthly_value) * 30 if monthly_value > 0 else 999
        fmt = self.estimator._format_usd
        total = annual_value if annual_value > 0 else 1
        result = {
            "vertical": vertical,
            "tier": self.tier,
            "monthly_cost_usd": self.monthly_cost,
            "monthly_value_protected_usd": round(monthly_value, 2),
            "annual_value_protected_usd": round(annual_value, 2),
            "roi_ratio": round(roi_ratio, 1),
            "payback_days": round(payback_days, 1),
            "annual_net_benefit_usd": round(annual_value - self.monthly_cost * 12, 2),
            "breakdown": {
                key: {
                    "annual_usd": round(value, 2),
                    "label": label,
                    "pct_of_total": round(value / total * 100, 1),
                }
                for key, (label, value) in breakdown.items()
            },
            "executive_summary": (
                f"Modelled: about {roi_ratio:.0f}x ROI, {fmt(monthly_value)}/month in value "
                f"on a {fmt(self.monthly_cost)}/month engagement through {pitch}. It pays for itself in "
                f"{payback_days:.0f} days, with {fmt(annual_value - self.monthly_cost * 12)} in net annual benefit."
                f" (A modelled estimate based on stated assumptions, not a measured result: model performance and loss "
                f"benchmarks are inputs; swap in your own measurements and sourced benchmarks.)"
            ),
            "details": details,
        }
        self._last_result = result
        return result

    def compute_gpu_roi(
        self,
        fleet_gpus: int = 256,
        current_utilization: float = 0.40,
        target_utilization: float = 0.70,
        on_prem: bool = False,
    ) -> dict[str, Any]:
        """ROI for a GPU / AI-infrastructure optimisation engagement."""
        gpu = self.estimator.estimate_gpu_optimization_impact(
            fleet_gpus=fleet_gpus,
            current_utilization=current_utilization,
            target_utilization=target_utilization,
            on_prem=on_prem,
        )
        return self._summarize(
            "gpu",
            gpu["annual_savings_usd"],
            {
                "capacity_reclaimed": (
                    "GPU Capacity Reclaimed (consolidation, MIG, idle)",
                    gpu["capacity_savings_usd"],
                ),
                "energy": ("Energy Saved (power capping)", gpu["energy_savings_usd"]),
            },
            {"gpu": gpu},
            "GPU consolidation, idle reclamation and power capping",
        )

    def compute_migration_roi(
        self,
        vm_count: int = 1_500,
        hosts: int | None = None,
        automation_ratio: float = 0.8,
        warm_migration_ratio: float = 0.6,
    ) -> dict[str, Any]:
        """First-year ROI for a VMware → OpenShift migration engagement."""
        mig = self.estimator.estimate_migration_impact(
            vm_count=vm_count,
            hosts=hosts,
            automation_ratio=automation_ratio,
            warm_migration_ratio=warm_migration_ratio,
        )
        return self._summarize(
            "migration",
            mig["first_year_value_usd"],
            {
                "licensing": ("VMware → OpenShift Licensing Delta", mig["annual_licensing_savings_usd"]),
                "labour": ("Automated Migration Labour Saved", mig["one_time_labour_savings_usd"]),
                "downtime": (
                    "Cutover Downtime Avoided (warm migration)",
                    mig["one_time_downtime_avoided_usd"],
                ),
            },
            {"migration": mig},
            "automated, low-downtime VMware → OpenShift migration and licensing consolidation",
        )

    def to_json(self) -> str:
        """Serialize the last computed ROI result to JSON."""
        if self._last_result is None:
            return json.dumps(
                {"error": "No ROI computed yet. Call compute_hospital_roi() or compute_bank_roi() first."}
            )
        return json.dumps(self._last_result, indent=2)

    @classmethod
    def quick_summary(cls, vertical: str, tier: str = "professional", **kwargs) -> dict[str, Any]:
        """Convenience method: compute and return ROI in one call."""
        calc = cls(vertical=vertical, tier=tier)
        dispatch: dict[str, Callable[..., dict[str, Any]]] = {
            "healthcare": calc.compute_hospital_roi,
            "fintech": calc.compute_bank_roi,
            "gpu": calc.compute_gpu_roi,
            "migration": calc.compute_migration_roi,
        }
        return dispatch[vertical](**kwargs)
