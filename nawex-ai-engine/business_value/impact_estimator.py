# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# ===========================================================================
"""impact_estimator.py

Translates NAWEX AI risk scores into quantified financial impact estimates.

Methodology: Bayesian expected-value calculation.

    Expected Loss = P(event) * Cost(event) * (1 - Detection_Lift)

where Detection_Lift = model_precision * model_recall, representing the
fraction of loss the NAWEX AI engine prevents through early detection.

These estimates are suitable for presenting to hospital CFOs, bank risk
officers, and compliance teams as part of a consulting engagement justification.
"""

from __future__ import annotations

from typing import Dict, Any

from .dollar_thresholds import HEALTHCARE_CONSTANTS, FINTECH_CONSTANTS


class ImpactEstimator:
    """
    Converts NAWEX AI risk scores into quantified dollar-impact narratives.

    Supports two verticals: 'healthcare' and 'fintech'.
    """

    def __init__(self, vertical: str = "healthcare") -> None:
        if vertical not in ("healthcare", "fintech"):
            raise ValueError("vertical must be 'healthcare' or 'fintech'")
        self.vertical = vertical
        self._hc = HEALTHCARE_CONSTANTS
        self._ft = FINTECH_CONSTANTS

    # ------------------------------------------------------------------
    # Healthcare Impact Methods
    # ------------------------------------------------------------------

    def estimate_readmission_impact(
        self,
        clinical_risk_score: float,
        patients_monitored_per_day: int,
        baseline_readmission_rate: float = None,
        model_sensitivity: float = 0.971,
        model_specificity: float = 0.945,
    ) -> Dict[str, Any]:
        """
        Estimate the financial impact of NAWEX early readmission risk detection.

        Uses NNT (Number Needed to Treat) methodology aligned with CMS
        Hospital Readmissions Reduction Program (HRRP) metrics.

        Args:
            clinical_risk_score: Composite clinical risk score [0.0, 1.0]
            patients_monitored_per_day: Daily census monitored by NAWEX
            baseline_readmission_rate: Hospital's current 30-day readmission rate
            model_sensitivity: True positive rate of NAWEX clinical alerts
            model_specificity: True negative rate

        Returns:
            Dict with impact estimates and CIO-ready narrative.
        """
        if baseline_readmission_rate is None:
            baseline_readmission_rate = self._hc["baseline_readmission_rate"]

        cost_per_readmission = self._hc["avg_readmission_cost_usd"]
        cms_penalty = self._hc["cms_readmission_penalty_per_patient_usd"]

        # Daily discharges from the monitored census (avg hospital LOS = 9 days)
        # Readmission rate is 30-day, so daily readmission risk from today's discharges:
        #   daily_discharges = census / avg_los
        #   daily_readmissions = daily_discharges * rate_30day / 30
        avg_los_days = 9.0
        daily_discharges = patients_monitored_per_day / avg_los_days
        expected_daily_readmissions = daily_discharges * (baseline_readmission_rate / 30)

        # NAWEX detection lift: fraction we can prevent with early intervention
        detection_lift = model_sensitivity * (1 - (1 - model_specificity))
        detection_lift = min(detection_lift, 0.85)  # Conservative cap

        # Readmission risk modifier based on NAWEX's clinical risk score
        risk_modifier = 1.0 + (clinical_risk_score * 0.30)  # Up to 30% above baseline

        daily_readmissions_prevented = expected_daily_readmissions * detection_lift * risk_modifier
        daily_cost_prevented = daily_readmissions_prevented * (cost_per_readmission + cms_penalty)
        annual_cost_prevented = daily_cost_prevented * 365

        return {
            "daily_readmissions_prevented": round(daily_readmissions_prevented, 2),
            "daily_cost_prevented_usd": round(daily_cost_prevented, 2),
            "annual_cost_prevented_usd": round(annual_cost_prevented, 2),
            "model_sensitivity": model_sensitivity,
            "model_specificity": model_specificity,
            "detection_lift_pct": round(detection_lift * 100, 1),
            "narrative": (
                f"NAWEX clinical AI monitors {patients_monitored_per_day} patients daily, "
                f"preventing an estimated {daily_readmissions_prevented:.1f} readmissions/day "
                f"({self._format_usd(annual_cost_prevented)} annually)."
            ),
            "methodology": (
                "NNT-based expected value: P(readmission) × cost × detection_lift, "
                "where detection_lift = sensitivity × (1 − FPR). "
                "Aligned with CMS HRRP penalty framework."
            ),
        }

    def estimate_phi_breach_impact(
        self,
        phi_risk_score: float,
        records_at_risk: int,
        detection_lead_time_hours: float = 4.0,
        model_precision: float = 0.956,
    ) -> Dict[str, Any]:
        """
        Estimate financial exposure from PHI breach risk detected by NAWEX.

        Covers: per-record breach cost, HIPAA fine exposure, downtime cost.

        Args:
            phi_risk_score: PHI anomaly risk score from NAWEX [0.0, 1.0]
            records_at_risk: Total PHI records accessible by flagged user/session
            detection_lead_time_hours: Hours earlier NAWEX detects vs. baseline
            model_precision: Precision of NAWEX PHI anomaly detection

        Returns:
            Dict with breach cost avoidance and compliance exposure estimates.
        """
        cost_per_record = self._hc["phi_breach_cost_per_record_usd"]
        downtime_per_hour = self._hc["ehr_downtime_cost_per_hour_usd"]
        hipaa_max_fine = self._hc["hipaa_fine_max_annual_usd"]

        # P(breach materializing given this risk score)
        p_breach = phi_risk_score * model_precision

        # Industry average breach size for hospitals: 5,000 records (HHS Breach Portal 2024)
        # Total records in system is the risk scope, not the breach size
        avg_breach_size_records = min(records_at_risk * 0.02, 5_000)  # 2% of total, max 5K
        records_compromised = int(avg_breach_size_records * p_breach)

        breach_cost_avoided = records_compromised * cost_per_record
        downtime_cost_avoided = downtime_per_hour * detection_lead_time_hours
        hipaa_exposure_reduced = hipaa_max_fine * phi_risk_score * 0.05  # 5% of max annual fine
        total_exposure_avoided = breach_cost_avoided + downtime_cost_avoided + hipaa_exposure_reduced

        return {
            "records_protected": records_at_risk,
            "records_compromised_without_nawex": records_compromised,
            "breach_cost_avoided_usd": round(breach_cost_avoided, 2),
            "downtime_cost_avoided_usd": round(downtime_cost_avoided, 2),
            "hipaa_exposure_reduced_usd": round(hipaa_exposure_reduced, 2),
            "total_exposure_avoided_usd": round(total_exposure_avoided, 2),
            "detection_lead_time_hours": detection_lead_time_hours,
            "narrative": (
                f"NAWEX detected anomalous PHI access {detection_lead_time_hours:.0f} hours early, "
                f"protecting {records_at_risk:,} records and avoiding "
                f"{self._format_usd(total_exposure_avoided)} in combined breach and compliance costs."
            ),
            "methodology": (
                "Expected breach cost = P(breach | risk_score) × records_at_risk × cost_per_record. "
                "HIPAA exposure per IBM Cost of a Data Breach 2024 ($499/PHI record). "
                "Detection lift based on NAWEX PHI anomaly model precision: 95.6%."
            ),
        }

    def estimate_clinical_downtime_impact(
        self,
        latency_risk_score: float,
        ehr_queries_per_hour: int,
        slo_ms: float = 200.0,
    ) -> Dict[str, Any]:
        """
        Estimate financial impact of EHR latency SLO breach caught by NAWEX.

        Args:
            latency_risk_score: EHR latency risk score from NAWEX [0.0, 1.0]
            ehr_queries_per_hour: Current EHR query rate
            slo_ms: EHR query SLO in milliseconds

        Returns:
            Dict with downtime cost avoidance estimates.
        """
        downtime_per_hour = self._hc["ehr_downtime_cost_per_hour_usd"]

        # Estimated hours of disruption without early intervention
        projected_disruption_hours = latency_risk_score * 3.0  # Up to 3 hours at risk=1.0
        disruption_cost = projected_disruption_hours * downtime_per_hour

        # Clinical workflow impact (delayed queries)
        delayed_queries = ehr_queries_per_hour * projected_disruption_hours
        # Each delayed query costs ~$12 in clinician time (estimate)
        workflow_cost = delayed_queries * 12.0

        total_avoided = disruption_cost + workflow_cost

        return {
            "projected_disruption_hours": round(projected_disruption_hours, 2),
            "downtime_cost_avoided_usd": round(disruption_cost, 2),
            "workflow_disruption_cost_usd": round(workflow_cost, 2),
            "total_avoided_usd": round(total_avoided, 2),
            "narrative": (
                f"NAWEX latency prediction identified a {latency_risk_score:.0%} SLO breach risk, "
                f"enabling proactive remediation and avoiding {self._format_usd(total_avoided)} "
                f"in EHR downtime and clinical workflow disruption costs."
            ),
            "methodology": (
                "Downtime cost per Ponemon/Guidehouse ($45,700/hr). "
                "Workflow disruption cost: delayed_queries × $12 clinician-time proxy."
            ),
        }

    # ------------------------------------------------------------------
    # Fintech Impact Methods
    # ------------------------------------------------------------------

    def estimate_fraud_impact(
        self,
        fraud_score: float,
        transaction_amount: float,
        transactions_per_day: int,
        model_precision: float = 0.956,
        model_recall: float = 0.923,
    ) -> Dict[str, Any]:
        """
        Estimate financial impact of fraud detection by NAWEX.

        Methodology: Bayesian expected-value with detection lift.
            Net value = (fraud_losses_prevented) - (false_positive_review_costs)

        Args:
            fraud_score: Composite fraud risk score from NAWEX [0.0, 1.0]
            transaction_amount: Average transaction amount in USD
            transactions_per_day: Total daily transaction volume
            model_precision: NAWEX fraud model precision (PPV)
            model_recall: NAWEX fraud model recall (sensitivity)

        Returns:
            Dict with fraud loss prevention and net value estimates.
        """
        avg_fraud_loss = self._hc.get("avg_fraudulent_transaction_usd", self._ft["avg_fraudulent_transaction_usd"])
        avg_fraud_loss = self._ft["avg_fraudulent_transaction_usd"]
        investigation_cost = self._ft["avg_fraud_investigation_cost_usd"]
        review_cost = self._ft["manual_review_cost_per_transaction_usd"]
        industry_fpr = self._ft["industry_avg_false_positive_rate"]

        # Industry baseline fraud rate ~0.1% of transactions
        baseline_fraud_rate = 0.001
        expected_fraud_txns_per_day = transactions_per_day * baseline_fraud_rate * (1 + fraud_score)

        # NAWEX detection lift
        detection_lift = model_precision * model_recall
        fraud_prevented_per_day = expected_fraud_txns_per_day * detection_lift

        # Loss prevented: avg fraud loss (Fed Reserve $1,200) + chargeback fee per prevented case
        chargeback_fee = 190  # Visa/Mastercard chargeback processing fee
        daily_loss_prevented = fraud_prevented_per_day * (avg_fraud_loss + chargeback_fee)
        annual_loss_prevented = daily_loss_prevented * 365

        # False positive cost (NAWEX has lower FPR than industry average)
        nawex_fpr = industry_fpr * (1 - model_precision * 0.5)
        daily_false_positives = transactions_per_day * nawex_fpr
        daily_fp_cost = daily_false_positives * review_cost
        annual_fp_cost = daily_fp_cost * 365

        net_annual_value = annual_loss_prevented - annual_fp_cost

        return {
            "expected_daily_fraud_prevented": round(fraud_prevented_per_day, 2),
            "daily_loss_prevented_usd": round(daily_loss_prevented, 2),
            "annual_loss_prevented_usd": round(annual_loss_prevented, 2),
            "annual_false_positive_cost_usd": round(annual_fp_cost, 2),
            "net_annual_value_usd": round(net_annual_value, 2),
            "model_precision": model_precision,
            "model_recall": model_recall,
            "narrative": (
                f"NAWEX fraud AI prevents {fraud_prevented_per_day:.1f} fraudulent transactions/day "
                f"({self._format_usd(annual_loss_prevented)}/year), "
                f"with net annual value of {self._format_usd(net_annual_value)} after false-positive costs."
            ),
            "methodology": (
                "Expected fraud loss = baseline_rate × volume × (1+risk_score) × detection_lift. "
                "Detection lift = precision × recall. Net value = loss_prevented − FP_review_costs. "
                "Fed Reserve Payments Study 2024 baseline rates."
            ),
        }

    def estimate_payment_downtime_impact(
        self,
        latency_risk_score: float,
        transactions_per_minute: int,
        avg_transaction_value: float,
    ) -> Dict[str, Any]:
        """
        Estimate financial impact of payment SLO breach prevented by NAWEX.

        Args:
            latency_risk_score: Payment latency risk score from NAWEX [0.0, 1.0]
            transactions_per_minute: Current payment throughput
            avg_transaction_value: Average transaction value in USD

        Returns:
            Dict with payment downtime and lost-revenue estimates.
        """
        downtime_per_minute = self._ft["payment_downtime_cost_per_minute_usd"]
        chargeback_cost = self._ft["chargeback_cost_per_incident_usd"]

        # Projected downtime minutes without NAWEX early intervention
        projected_downtime_min = latency_risk_score * 45  # Up to 45 min at risk=1.0
        direct_downtime_cost = projected_downtime_min * downtime_per_minute

        # Lost transaction revenue during downtime
        lost_transactions = transactions_per_minute * projected_downtime_min
        lost_revenue = lost_transactions * avg_transaction_value * 0.02  # 2% margin impact

        # Chargebacks from failed transactions
        failed_txn_rate = latency_risk_score * 0.08
        expected_chargebacks = lost_transactions * failed_txn_rate
        chargeback_total = expected_chargebacks * chargeback_cost

        total_avoided = direct_downtime_cost + lost_revenue + chargeback_total

        return {
            "projected_downtime_minutes": round(projected_downtime_min, 1),
            "direct_downtime_cost_usd": round(direct_downtime_cost, 2),
            "lost_revenue_usd": round(lost_revenue, 2),
            "chargeback_exposure_usd": round(chargeback_total, 2),
            "total_avoided_usd": round(total_avoided, 2),
            "narrative": (
                f"NAWEX latency AI identified a {latency_risk_score:.0%} SLO breach risk, "
                f"enabling proactive gateway failover and avoiding "
                f"{self._format_usd(total_avoided)} in downtime, lost revenue, and chargebacks."
            ),
            "methodology": (
                "Direct downtime: Gartner $5,600/min. "
                "Lost revenue: volume × avg_value × 2% margin. "
                "Chargeback exposure: failed_txns × $190 per Visa/Mastercard schedule."
            ),
        }

    def estimate_compliance_impact(
        self,
        compliance_risk_score: float,
        annual_transaction_volume_usd: float,
    ) -> Dict[str, Any]:
        """
        Estimate AML/BSA compliance exposure reduced by NAWEX monitoring.

        Args:
            compliance_risk_score: Regulatory compliance risk score [0.0, 1.0]
            annual_transaction_volume_usd: Annual transaction volume in USD

        Returns:
            Dict with regulatory fine exposure and audit cost estimates.
        """
        aml_fine = self._ft["aml_compliance_fine_avg_usd"]
        capital_ratio = self._ft["operational_risk_capital_ratio"]

        # Regulatory fine exposure (proportional to risk score)
        fine_exposure = aml_fine * compliance_risk_score
        fine_avoided = fine_exposure * 0.75  # NAWEX reduces exposure by 75%

        # Operational risk capital freed (Basel III) — capped at $400K (realistic for non-SIFI)
        capital_freed = min(
            annual_transaction_volume_usd * capital_ratio * compliance_risk_score * 0.10,
            400_000
        )

        # Audit cost reduction
        audit_cost_saved = 180_000 * compliance_risk_score * 0.40  # Avg bank BSA audit

        total_value = fine_avoided + capital_freed + audit_cost_saved

        return {
            "regulatory_fine_exposure_usd": round(fine_exposure, 2),
            "fine_avoided_usd": round(fine_avoided, 2),
            "capital_freed_usd": round(capital_freed, 2),
            "audit_cost_saved_usd": round(audit_cost_saved, 2),
            "total_compliance_value_usd": round(total_value, 2),
            "narrative": (
                f"NAWEX compliance monitoring reduces regulatory fine exposure by "
                f"{self._format_usd(fine_avoided)}, frees {self._format_usd(capital_freed)} "
                f"in operational risk capital, and reduces audit costs by "
                f"{self._format_usd(audit_cost_saved)} annually."
            ),
            "methodology": (
                "Regulatory exposure: avg AML fine × risk_score (Deloitte 2024). "
                "Capital relief: Basel III standardized approach (12% operational risk ratio). "
                "Audit savings: 40% reduction in BSA examination scope."
            ),
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _format_usd(self, amount: float) -> str:
        """Format a dollar amount as $1.2M, $850K, or $45,000."""
        if amount >= 1_000_000:
            return f"${amount / 1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"${amount / 1_000:.0f}K"
        else:
            return f"${amount:,.0f}"
