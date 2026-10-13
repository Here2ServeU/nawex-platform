"""FinOps: FOCUS loading, showback/chargeback, anomalies/forecast/budgets, recommendations, k8s allocation."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from golden.finops import (
    FOCUS_COLUMNS,
    Node,
    Pod,
    ResourceUtilization,
    allocate,
    allocate_cluster_cost,
    breakdown,
    budget_status,
    chargeback,
    commitment_recommendation,
    daily_costs,
    detect_anomalies,
    finops_report,
    forecast_month_end,
    load_focus,
    parse_tags,
    rightsizing,
    sample_cluster,
    sample_focus_data,
    sample_hourly_compute_spend,
    sample_utilization,
    showback,
    tag_coverage,
    tag_value,
    to_focus_csv,
    unit_economics,
)
from golden.finops.anomalies import robust_z
from golden.finops.recommendations import IDLE, history_confidence

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def focus() -> pd.DataFrame:
    return sample_focus_data()


def _frame(rows: list[tuple[str, float, dict[str, str]]], service: str = "Amazon EC2") -> pd.DataFrame:
    """(day, cost, tags) rows -> minimal FOCUS frame."""
    return load_focus(
        pd.DataFrame(
            {
                "ChargePeriodStart": [d for d, _, _ in rows],
                "EffectiveCost": [c for _, c, _ in rows],
                "ServiceName": [service] * len(rows),
                "ProviderName": ["AWS"] * len(rows),
                "Tags": [json.dumps(t) for _, _, t in rows],
            }
        )
    )


# ----------------------------------------------------------------------------- FOCUS loading
def test_sample_covers_three_clouds_teams_untagged_and_anomaly(focus: pd.DataFrame) -> None:
    assert list(focus.columns) == list(FOCUS_COLUMNS)
    assert set(focus["ProviderName"]) == {"AWS", "Microsoft", "Google Cloud"}
    teams = {tag_value(t, "Team") for t in focus["Tags"]}
    assert {"payments", "search", "ml", "data-platform", "shared", None} <= teams
    spike = focus[(focus["ResourceId"] == "i-payments-api")].set_index("ChargePeriodStart")["EffectiveCost"]
    assert spike[pd.Timestamp("2026-09-22")] > 3 * spike.median()
    # Deterministic for a given seed.
    assert sample_focus_data()["EffectiveCost"].sum() == pytest.approx(focus["EffectiveCost"].sum())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"Team": "payments", "Owner": "a"}', {"Team": "payments", "Owner": "a"}),
        ('"team": "search","env": "prod"', {"team": "search", "env": "prod"}),  # Azure export
        ('[{"key": "team", "value": "ml"}]', {"team": "ml"}),  # GCP labels
        ("Team=payments;CostCenter=cc-1", {"Team": "payments", "CostCenter": "cc-1"}),
        ("", {}),
        (None, {}),
        (float("nan"), {}),
        ("{}", {}),
    ],
)
def test_parse_tags_across_provider_formats(raw: object, expected: dict[str, str]) -> None:
    assert parse_tags(raw) == expected


def test_focus_csv_round_trip(tmp_path: Path, focus: pd.DataFrame) -> None:
    path = tmp_path / "focus.csv"
    to_focus_csv(focus, path)
    loaded = load_focus(path)
    assert len(loaded) == len(focus)
    assert loaded["EffectiveCost"].sum() == pytest.approx(focus["EffectiveCost"].sum(), rel=1e-9)
    assert loaded["Tags"].iloc[0] == focus["Tags"].iloc[0]
    assert loaded["ChargePeriodStart"].min() == pd.Timestamp("2026-09-01")


def test_native_exports_map_onto_focus() -> None:
    aws = load_focus(
        "line_item_usage_start_date,line_item_unblended_cost,product_product_name,line_item_usage_account_id,"
        "product_region_code,line_item_resource_id,resource_tags\n"
        '2026-09-01T00:00:00Z,12.5,Amazon Simple Storage Service,111,us-east-1,bkt,"{""user:Team"": ""payments""}"\n'
    )
    azure = load_focus(
        "Date,CostInBillingCurrency,MeterCategory,SubscriptionId,ResourceLocation,ResourceId,Tags\n"
        '09/02/2026,7.25,Virtual Network,sub-1,eastus,/subs/x,"""Team"": ""search"""\n'
    )
    gcp = load_focus(
        "usage_start_time,cost,service_description,project_id,location_region,labels\n"
        '2026-09-03 00:00:00 UTC,3.0,BigQuery,proj-1,us-central1,"[{""key"": ""team"", ""value"": ""ml""}]"\n'
    )
    assert aws.loc[0, "ProviderName"] == "AWS" and aws.loc[0, "BilledCost"] == 12.5
    assert aws.loc[0, "ServiceCategory"] == "Storage"
    assert azure.loc[0, "ProviderName"] == "Microsoft"
    assert azure.loc[0, "ServiceCategory"] == "Networking"
    assert tag_value(azure.loc[0, "Tags"], "Team") == "search"
    assert gcp.loc[0, "ProviderName"] == "Google Cloud" and gcp.loc[0, "ServiceCategory"] == "Analytics"
    assert gcp.loc[0, "EffectiveCost"] == gcp.loc[0, "ListCost"] == 3.0
    assert gcp.loc[0, "ChargePeriodStart"] == pd.Timestamp("2026-09-03")


def test_load_rejects_data_without_cost_or_date() -> None:
    with pytest.raises(ValueError, match="no cost column"):
        load_focus("ChargePeriodStart,ServiceName\n2026-09-01,EC2\n")
    with pytest.raises(ValueError, match="charge date"):
        load_focus("BilledCost,ServiceName\n1.0,EC2\n")


# ----------------------------------------------------------------------------- tagging + allocation
def test_tag_coverage_flags_untagged_spend(focus: pd.DataFrame) -> None:
    coverage = tag_coverage(focus)
    assert 0.9 < coverage.coverage < 0.97
    offenders = [r["resource"] for r in coverage.untagged_resources]
    assert offenders[0] == "i-0orphan"
    assert {"vol-0unattached", "vm-legacy-jump", "vm-test-forgotten"} <= set(offenders)
    # GCP lowercase/snake_case labels satisfy CostCenter etc.
    gcp = focus[focus["ProviderName"] == "Google Cloud"]
    assert tag_coverage(gcp[gcp["ResourceId"] != "vm-test-forgotten"]).coverage == 1.0


def test_tag_value_is_case_and_separator_insensitive() -> None:
    assert tag_value({"cost_center": "cc-1"}, "CostCenter") == "cc-1"
    assert tag_value({"Cost-Center": "cc-2"}, "costcenter") == "cc-2"
    assert tag_value({"Team": "  "}, "Team") is None
    assert tag_value(None, "Team") is None


def test_showback_conserves_cost_and_keeps_untagged_visible(focus: pd.DataFrame) -> None:
    result = showback(focus)
    totals = result.totals()
    assert sum(o.total for o in result.owners) == pytest.approx(result.total_cost)
    assert totals["untagged"] == pytest.approx(result.untagged_pool, abs=0.01)
    assert "shared" not in totals
    assert result.shared_pool > 0
    payments = result.owner("payments")
    assert payments is not None
    # Proportional: shared share == direct share among tagged owners.
    direct_total = sum(o.direct for o in result.owners)
    assert payments.shared / result.shared_pool == pytest.approx(payments.direct / direct_total)


def test_chargeback_invoices_every_dollar(focus: pd.DataFrame) -> None:
    result = chargeback(focus)
    assert result.owner("untagged") is None
    assert sum(o.total for o in result.owners) == pytest.approx(float(focus["EffectiveCost"].sum()))
    assert all(o.untagged > 0 for o in result.owners)


def test_even_and_fixed_shared_cost_methods(focus: pd.DataFrame) -> None:
    even = allocate(focus, method="even")
    shares = {o.owner: o.shared for o in even.owners if o.owner != "untagged"}
    assert len(set(round(v, 6) for v in shares.values())) == 1

    fixed = allocate(focus, method="fixed", weights={"payments": 3, "search": 1})
    assert fixed.owner("payments").shared == pytest.approx(0.75 * fixed.shared_pool)  # type: ignore[union-attr]
    assert fixed.owner("ml").shared == 0  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="no direct spend"):
        allocate(focus, method="fixed", weights={"nobody": 1})
    with pytest.raises(ValueError, match="needs weights"):
        allocate(focus, method="fixed")


def test_shared_services_by_category(focus: pd.DataFrame) -> None:
    base = allocate(focus)
    widened = allocate(focus, shared_services={"Networking", "Management and Governance"})
    assert widened.shared_pool >= base.shared_pool
    networking = focus[focus["ServiceCategory"].isin({"Networking", "Management and Governance"})]
    assert widened.shared_pool >= float(networking["EffectiveCost"].sum()) - 1e-6


def test_allocation_with_nothing_tagged() -> None:
    frame = _frame([("2026-09-01", 10.0, {}), ("2026-09-02", 5.0, {})])
    for mode in ("showback", "chargeback"):
        result = allocate(frame, mode=mode)  # type: ignore[arg-type]
        assert result.totals() == {"untagged": 15.0}


def test_breakdowns_by_provider_and_team(focus: pd.DataFrame) -> None:
    by_provider = breakdown(focus, "ProviderName")
    assert by_provider["share"].sum() == pytest.approx(1.0)
    assert by_provider.iloc[0]["ProviderName"] == "AWS"
    by_team = breakdown(focus, ["ProviderName", "Team"])
    assert {"untagged", "shared", "payments"} <= set(by_team["Team"])


def test_unit_economics_cost_per_thousand(focus: pd.DataFrame) -> None:
    result = chargeback(focus)
    units = {
        u.owner: u for u in unit_economics(result, {"payments": 1_000_000, "total": 2_000_000, "ghost": 5})
    }
    assert set(units) == {"payments", "total"}
    payments = units["payments"]
    assert payments.cost_per_n == pytest.approx(result.totals()["payments"] / 1000, rel=1e-6)
    assert units["total"].cost == pytest.approx(result.total_cost, abs=0.05)
    assert unit_economics({"a": 10.0}, {"a": 0})[0].cost_per_unit == float("inf")


# ----------------------------------------------------------------------------- anomalies, forecast, budgets
def test_detects_the_injected_spike_by_service_and_team(focus: pd.DataFrame) -> None:
    by_service = detect_anomalies(focus, "ServiceName")
    by_team = detect_anomalies(focus, "Team")
    assert [(a.date, a.group) for a in by_service] == [("2026-09-22", "Amazon EC2")]
    assert [(a.date, a.group) for a in by_team] == [("2026-09-22", "payments")]
    spike = by_team[0]
    assert spike.severity == "high" and spike.impact > 1000
    assert json.dumps(spike.to_dict())  # plain JSON types


def test_no_anomalies_in_clean_data() -> None:
    assert detect_anomalies(sample_focus_data(anomaly_day=None), "ServiceName") == []
    assert detect_anomalies(sample_focus_data(anomaly_day=None), "Team") == []


def test_small_spikes_below_min_impact_ignored() -> None:
    rows = [(f"2026-09-{d:02d}", 10.0, {"Team": "a"}) for d in range(1, 15)] + [
        ("2026-09-15", 30.0, {"Team": "a"})
    ]
    frame = _frame(rows)
    assert detect_anomalies(frame, "Team") == []
    assert [a.date for a in detect_anomalies(frame, "Team", min_impact=5)] == ["2026-09-15"]


def test_robust_z_floor_for_flat_history() -> None:
    z, median = robust_z(101.0, np.full(14, 100.0))
    assert median == 100.0 and z == pytest.approx(0.2)  # scale floored at 5% of median


def test_daily_costs_fills_gaps() -> None:
    frame = _frame([("2026-09-01", 1.0, {}), ("2026-09-04", 2.0, {})])
    table = daily_costs(frame)
    assert list(table["total"]) == [1.0, 0.0, 0.0, 2.0]


def test_forecast_linear_trend() -> None:
    # Daily cost = 100 + 10 * day, observed through day 10 of a 30-day month.
    rows = [(f"2026-09-{d:02d}", 100.0 + 10 * d, {}) for d in range(1, 21)]
    fc = forecast_month_end(_frame(rows), as_of=date(2026, 9, 10))
    expected = sum(100.0 + 10 * d for d in range(1, 31))
    assert fc.days_elapsed == 10 and fc.days_in_month == 30
    assert fc.month_to_date == pytest.approx(sum(100.0 + 10 * d for d in range(1, 11)))
    assert fc.forecast == pytest.approx(expected, rel=1e-6)
    assert fc.daily_trend == pytest.approx(10.0)


def test_forecast_early_month_uses_run_rate() -> None:
    fc = forecast_month_end(_frame([("2026-09-01", 50.0, {}), ("2026-09-02", 70.0, {})]))
    assert fc.forecast == pytest.approx(60.0 * 30)


def test_budget_status_ladder(focus: pd.DataFrame) -> None:
    as_of = date(2026, 9, 15)
    mtd = {
        s.name: s.month_to_date
        for s in budget_status(focus, {"payments": 1e9, "search": 1e9, "ml": 1e9, "total": 1e9}, as_of=as_of)
    }
    budgets = {
        "payments": mtd["payments"] * 0.9,  # already over
        "search": mtd["search"] * 1.5,  # forecast ~2x MTD -> at risk
        "ml": mtd["ml"] * 1.2,  # under budget today, forecast ~2x MTD -> at risk
        "total": mtd["total"] * 10,
    }
    status = {s.name: s.status for s in budget_status(focus, budgets, as_of=as_of)}
    assert status == {"payments": "over", "search": "at_risk", "ml": "at_risk", "total": "ok"}
    month = float(focus["EffectiveCost"].sum())
    warning = budget_status(focus, {"total": month * 1.1}, as_of=date(2026, 9, 30))
    assert warning[0].status == "warning"


# ----------------------------------------------------------------------------- recommendations
def test_rightsizing_finds_idle_and_overprovisioned() -> None:
    recs = {r.resource_id: r for r in rightsizing(sample_utilization())}
    assert recs["i-0orphan"].kind == "terminate-idle"
    assert recs["i-0orphan"].estimated_monthly_savings == pytest.approx(0.384 * 730, abs=0.01)
    assert recs["i-search-nodes"].kind == "rightsize"
    assert recs["i-search-nodes"].evidence["target_vcpus"] == 8
    assert recs["i-search-nodes"].estimated_monthly_savings == pytest.approx(0.768 * 730 / 2, abs=0.01)
    assert "i-payments-api" not in recs  # well sized
    assert "vm-etl-01" not in recs  # memory bound: low CPU alone does not justify downsizing
    assert all(r.confidence == "high" for r in recs.values())


def test_rightsizing_confidence_tracks_history() -> None:
    assert history_confidence(24) == "low"
    assert history_confidence(7 * 24) == "medium"
    assert history_confidence(30 * 24) == "high"
    short = ResourceUtilization("i-x", "m6i.xlarge", 0.192, 4, [1.0] * 48)
    assert rightsizing([short])[0].confidence == "low"


def test_commitment_sized_to_p10_baseline() -> None:
    spend = sample_hourly_compute_spend()
    rec = commitment_recommendation(spend, discount=0.3)
    assert rec is not None
    baseline = float(np.percentile(spend, 10))
    assert rec.evidence["baseline_hourly"] == pytest.approx(baseline, abs=1e-3)
    assert rec.estimated_monthly_savings == pytest.approx(baseline * 0.3 * 730, rel=1e-3)
    assert 0.6 < rec.evidence["coverage_after"] < 0.8
    assert rec.confidence == "high"
    assert commitment_recommendation(spend, current_commitment=100.0) is None
    assert commitment_recommendation([]) is None
    spiky = commitment_recommendation([1.0, 1.0, 50.0] * 10)
    assert spiky is not None and spiky.confidence == "low"


def test_kubernetes_allocation_conserves_node_cost() -> None:
    nodes, pods = sample_cluster()
    result = allocate_cluster_cost(nodes, pods)
    assert sum(result.hourly.values()) == pytest.approx(result.total_hourly)
    assert result.total_hourly == pytest.approx(0.768)
    assert IDLE in result.hourly and 0 < result.idle_ratio < 1
    shared = allocate_cluster_cost(nodes, pods, share_idle=True)
    assert IDLE not in shared.hourly and shared.idle_ratio == 0
    assert sum(shared.hourly.values()) == pytest.approx(0.768)
    assert shared.hourly["payments"] / shared.hourly["search"] == pytest.approx(
        result.hourly["payments"] / result.hourly["search"]
    )


def test_kubernetes_usage_above_request_and_overcommit() -> None:
    node = Node("n", 1.0, 4, 16)
    base = allocate_cluster_cost([node], [Pod("a", "n", 1, 4), Pod("b", "n", 1, 4)])
    bursty = allocate_cluster_cost([node], [Pod("a", "n", 1, 4, cpu_usage=3), Pod("b", "n", 1, 4)])
    assert bursty.hourly["a"] > base.hourly["a"]
    over = allocate_cluster_cost([node], [Pod("a", "n", 8, 32), Pod("b", "n", 8, 32)])
    assert over.hourly == {"a": pytest.approx(0.5), "b": pytest.approx(0.5)}
    assert over.idle_hourly == pytest.approx(0.0, abs=1e-12)


# ----------------------------------------------------------------------------- report + infrastructure
def test_sample_report_is_json_and_complete() -> None:
    report = json.loads(json.dumps(finops_report()))
    assert {
        "tag_coverage",
        "showback",
        "chargeback",
        "unit_economics",
        "anomalies",
        "forecast",
        "budgets",
        "recommendations",
        "kubernetes",
    } <= set(report)
    assert report["anomalies"]["by_team"][0]["group"] == "payments"
    assert {b["status"] for b in report["budgets"]} >= {"over", "ok"}


def test_report_from_csv_skips_samples(tmp_path: Path) -> None:
    path = tmp_path / "focus.csv"
    to_focus_csv(sample_focus_data(days=10), path)
    report = finops_report(path, budgets={"total": 1.0})
    assert "recommendations" not in report
    assert report["budgets"][0]["status"] == "over"
    assert report["period"] == {
        "start": "2026-09-01",
        "end": (date(2026, 9, 1) + timedelta(days=9)).isoformat(),
    }


@pytest.mark.parametrize("cloud", ["aws", "azure", "gcp"])
def test_terraform_modules_document_every_variable_and_output(cloud: str) -> None:
    module = ROOT / "deploy" / "terraform" / "modules" / cloud / "finops"
    for name in ("main.tf", "variables.tf", "outputs.tf", "versions.tf"):
        assert (module / name).is_file(), name
    assert (module / "main.tf").read_text().startswith("# ---")
    for name, kind in (("variables.tf", "variable"), ("outputs.tf", "output")):
        blocks = re.split(rf'^{kind} "', (module / name).read_text(), flags=re.M)[1:]
        assert blocks, name
        for block in blocks:
            assert "description" in block.split("\n}\n")[0], f"{cloud}/{name}: {block.split(chr(34))[0]}"
    variables = (module / "variables.tf").read_text()
    assert re.search(r'required_(tags|labels)"', variables)


def test_opa_tagging_policy_matches_python_defaults() -> None:
    rego = (ROOT / "security" / "policies" / "opa" / "tagging.rego").read_text()
    from golden.finops import DEFAULT_REQUIRED_TAGS

    defaults = re.search(r"default required_tags := \{([^}]*)\}", rego)
    assert defaults is not None
    assert set(re.findall(r'"(\w+)"', defaults.group(1))) == set(DEFAULT_REQUIRED_TAGS)
