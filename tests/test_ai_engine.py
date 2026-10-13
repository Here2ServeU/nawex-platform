from __future__ import annotations

import pandas as pd
import pytest

from golden.ai.agents import AnalyzerAgent, ExecutorAgent, Orchestrator, PlannerAgent
from golden.ai.business_value import ImpactEstimator, ROICalculator
from golden.ai.business_value.impact_estimator import format_usd
from golden.ai.classification import classify_incident
from golden.ai.datasets import (
    make_fraud_scenario_stream,
    make_patient_vitals_stream,
    make_phi_access_log,
    make_sli_dataset,
)
from golden.ai.evaluation import classification_metrics, regression_metrics
from golden.ai.explainability import build_text_report, normalize_contributions
from golden.ai.inference import aggregate_risk, run_all_predictors
from golden.ai.pipelines.clinical_risk import news2
from golden.ai.pipelines.detect_fraud import (
    calculate_fraud_score,
    detect_transaction_anomalies,
    fraud_signals,
)
from golden.ai.pipelines.detect_phi_anomalies import calculate_phi_risk_score, detect_patient_safety_risk
from golden.ai.prediction import predict_lstm, predict_tcn
from golden.ai.remediation import HANDLERS, execute_action, load_rules
from golden.security import ACTION_CATALOG, GuardrailViolation


# ----------------------------------------------------------------------------- business value
@pytest.mark.parametrize("vertical", ["healthcare", "fintech", "gpu", "migration"])
@pytest.mark.parametrize("tier", ["starter", "professional", "enterprise"])
def test_roi_every_vertical_and_tier(vertical, tier):
    roi = ROICalculator.quick_summary(vertical, tier=tier)
    assert roi["vertical"] == vertical
    assert roi["roi_ratio"] > 1 and roi["payback_days"] > 0
    assert abs(sum(b["pct_of_total"] for b in roi["breakdown"].values()) - 100) < 1.0
    assert "NAWEX" not in roi["executive_summary"]


def test_roi_rejects_unknown_inputs():
    with pytest.raises(ValueError):
        ROICalculator(vertical="retail")
    with pytest.raises(ValueError):
        ROICalculator(tier="platinum")


def test_gpu_impact_monotonic_in_utilisation():
    est = ImpactEstimator("gpu")
    low = est.estimate_gpu_optimization_impact(fleet_gpus=100, current_utilization=0.3)
    high = est.estimate_gpu_optimization_impact(fleet_gpus=100, current_utilization=0.6)
    assert low["gpus_freed"] > high["gpus_freed"] > 0


def test_migration_impact_scales_with_vms():
    est = ImpactEstimator("migration")
    small, large = est.estimate_migration_impact(100), est.estimate_migration_impact(1000)
    assert large["annual_licensing_savings_usd"] > small["annual_licensing_savings_usd"] > 0


@pytest.mark.parametrize(("amount", "text"), [(1_500_000, "$1.5M"), (85_000, "$85K"), (450, "$450")])
def test_format_usd(amount, text):
    assert format_usd(amount) == text


# ----------------------------------------------------------------------------- detection pipelines
def test_fraud_signals_are_explainable_and_bounded():
    risky = {
        "amount": 4000,
        "channel": "card_not_present",
        "country_code": "NG",
        "merchant_category_code": "7995",
    }
    safe = {"amount": 20, "channel": "pos", "country_code": "US", "merchant_category_code": "5411"}
    assert set(fraud_signals(risky)) == {"amount", "velocity", "geo", "channel", "mcc"}
    assert 0 <= calculate_fraud_score(safe) < calculate_fraud_score(risky) <= 1


def test_velocity_signal_uses_history():
    now = pd.Timestamp("2026-01-01 12:00", tz="UTC")
    history = pd.DataFrame(
        {"timestamp": [now - pd.Timedelta(minutes=i) for i in range(30)], "amount": [50.0] * 30}
    )
    assert fraud_signals({"amount": 50}, history, now=now)["velocity"] == 1.0


def test_batch_fraud_detection():
    scored = detect_transaction_anomalies(make_fraud_scenario_stream(n_transactions=120, seed=1))
    assert {"fraud_score", "is_flagged"} <= set(scored.columns)
    assert scored["fraud_score"].between(0, 1).all()


def test_phi_risk_orders_behaviour():
    benign = {"record_count": 1, "access_type": "read", "role": "nurse"}
    hostile = {
        "record_count": 500,
        "access_type": "bulk_export",
        "role": "contractor",
        "is_after_hours": True,
        "is_weekend": True,
        "cross_department": True,
    }
    assert calculate_phi_risk_score(benign) < calculate_phi_risk_score(hostile)


def test_patient_safety_risk():
    result = detect_patient_safety_risk(make_patient_vitals_stream(n_patients=10, n_timepoints=5, seed=3))
    assert result["total_patients_monitored"] == 10
    assert result["level"] in {"low", "high", "critical"}


@pytest.mark.parametrize(
    ("vitals", "score", "level"),
    [
        (dict(respiratory_rate=16, spo2=98, systolic_bp=120, heart_rate=70, temperature=37.0), 0, "low"),
        (dict(respiratory_rate=26, spo2=90, systolic_bp=88, heart_rate=135, temperature=39.5), 14, "high"),
        (
            dict(
                respiratory_rate=16,
                spo2=98,
                systolic_bp=120,
                heart_rate=70,
                temperature=37.0,
                consciousness="voice",
            ),
            3,
            "medium",
        ),  # any single parameter scoring 3 escalates
    ],
)
def test_news2(vitals, score, level):
    result = news2(**vitals)
    assert (result.score, result.level) == (score, level)


# ----------------------------------------------------------------------------- prediction & inference
def test_predictors_fallback_without_models():
    rising = [100, 100, 100, 100, 180]
    assert 0 < predict_lstm(rising) <= 1
    assert 0 < predict_tcn([100, 120, 150, 190]) <= 1
    assert predict_lstm([1, 2]) == 0.0


def test_predictors_apply_guardrails():
    with pytest.raises(GuardrailViolation):
        predict_lstm([1, 2, float("nan")])


def test_inference_aggregate():
    seq = [float(v) for v in make_sli_dataset(n_rows=40)["latency_ms"]]
    scores = run_all_predictors(seq)
    assert set(scores) == {"lstm_score", "tcn_score"}
    assert 0 <= aggregate_risk(scores) <= 1
    assert aggregate_risk({"a": 5.0}) == 1.0  # capped
    assert aggregate_risk({}) == 0.0


def test_metrics_and_explainability():
    assert regression_metrics([1, 2, 3], [1, 2, 3])["rmse"] == 0
    assert classification_metrics([1, 0, 1], [1, 0, 0])["precision"] == 1.0
    assert sum(normalize_contributions({"a": 1, "b": -3}).values()) == pytest.approx(1.0)
    assert build_text_report({"a": 3, "b": 1}).splitlines()[1] == "- a: 75.00%"


@pytest.mark.parametrize(
    ("signal", "expected"),
    [
        ({"phi_anomaly_score": 0.9}, "security.phi_breach"),
        ({"fraud_score": 0.95}, "security.fraud"),
        ({"ecc_errors": 2}, "gpu.hardware"),
        ({"gpu_temperature_c": 91}, "gpu.thermal"),
        ({"migration_validation": "failed"}, "migration.validation_failure"),
        ({"latency_ms": 900}, "reliability.critical_outage"),
        ({"latency_ms": 300}, "reliability.degradation"),
        ({"gpu_utilization_pct": 10}, "gpu.efficiency"),
        ({"latency_ms": 10}, "operations.investigate"),
        ({}, "unknown"),
    ],
)
def test_classify_incident(signal, expected):
    assert classify_incident(signal) == expected


# ----------------------------------------------------------------------------- remediation & agents
def test_every_rule_action_is_governed_and_handled():
    for rule in load_rules()["rules"]:
        assert rule["action"] in ACTION_CATALOG, rule
        assert rule["action"] in HANDLERS, rule
    assert set(HANDLERS) == set(ACTION_CATALOG)


def test_execute_action():
    assert execute_action({"action": "set_gpu_power_cap", "params": {"cap_pct_of_tdp": 75}})
    assert not execute_action("does_not_exist")


def test_agent_pipeline_respects_governor(governor):
    analysis = AnalyzerAgent({"thresholds": {"latency_ms": 200}}).analyze(
        {"latency_ms": 450, "error_rate_percent": 9, "timestamp": "t"}
    )
    assert analysis["status"] == "risk_detected"
    assert analysis["risk_flags"]["latency_risk"] == "critical"
    plan = PlannerAgent().plan(analysis)
    assert {a["action"] for a in plan["planned_actions"]} >= {"scale_up_replicas", "restart_service"}
    report = ExecutorAgent(governor=governor).execute(plan)
    assert report["executed"] == [] and len(report["simulated"]) == len(plan["planned_actions"])  # dry_run


def test_healthy_metrics_need_no_plan():
    analysis = AnalyzerAgent({}).analyze({"latency_ms": 100, "error_rate_percent": 0.1})
    assert analysis["status"] == "healthy"
    assert PlannerAgent().plan(analysis)["status"] == "no_action_needed"


def test_orchestrator_runs_bounded_cycles():
    results = Orchestrator().run(cycles=3, interval=0)
    assert len(results) == 3
    assert all("execution" in r for r in results)


def test_simulators_are_reproducible():
    a = make_phi_access_log(n_events=50, seed=7)
    b = make_phi_access_log(n_events=50, seed=7)
    pd.testing.assert_frame_equal(a.drop(columns="timestamp"), b.drop(columns="timestamp"))


@pytest.mark.parametrize("action", sorted(HANDLERS))
def test_every_remediation_handler_runs(action):
    assert execute_action({"action": action, "params": {"targets": ["a"], "node": "n1", "plan": "wave-00"}})
