"""Database performance & optimization advisors (golden.database)."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

from golden.database import (
    Finding,
    analyse_indexes,
    analyse_plan,
    analyse_workload,
    assess_capacity,
    autovacuum_settings,
    filter_columns,
    fingerprint,
    load_plan,
    load_price_table,
    load_statements,
    memory_parameters,
    parse_indexdef,
    parse_statements,
    partitioning_plan,
    pool_sizing,
    read_scaling,
    rightsize,
    sample_capacity_profile,
    sample_explain_plans,
    sample_index_snapshot,
    sample_statements,
    severity_counts,
    sort_findings,
)

REPO = Path(__file__).resolve().parents[1]


def codes(findings: list[Finding]) -> list[str]:
    return [f.code for f in findings]


@pytest.fixture(scope="module")
def workload():
    return analyse_workload(parse_statements(sample_statements()))


@pytest.fixture(scope="module")
def plans():
    return sample_explain_plans()


@pytest.fixture(scope="module")
def index_report():
    return analyse_indexes(sample_index_snapshot())


# --------------------------------------------------------------------------- findings
def test_finding_rejects_unknown_severity():
    with pytest.raises(ValueError):
        Finding("X", "urgent", "m", "r")


def test_sort_and_count_findings():
    fs = [Finding("A", "low", "", ""), Finding("B", "critical", "", ""), Finding("C", "medium", "", "")]
    assert codes(sort_findings(fs)) == ["B", "C", "A"]
    assert severity_counts(fs) == {"critical": 1, "high": 0, "medium": 1, "low": 1, "info": 0}


# --------------------------------------------------------------------------- workload
def test_fingerprint_collapses_literals_params_and_in_lists():
    a = fingerprint("SELECT * FROM payments WHERE id IN ($1, $2, $3) -- api")
    b = fingerprint("select *  from payments where id in (7, 8, 9, 10);")
    assert a == b == "select * from payments where id in (...)"
    assert (
        fingerprint("SELECT 1 FROM t WHERE email = 'x@y.z' AND n > 3.5")
        == "select ? from t where email = ? and n > ?"
    )


def test_fingerprint_keeps_identifiers_with_digits():
    assert "table_v2" in fingerprint("SELECT * FROM table_v2 WHERE id = 5")


def test_workload_totals_and_top_offender(workload):
    assert workload.totals["statements"] == len(sample_statements())
    assert workload.top_by_total_time[0]["queryid"] == "-4404"  # lower(email) Seq Scan
    assert workload.top_by_mean_time[0]["queryid"] == "-2208"  # settlement report
    assert workload.totals["cache_hit_ratio"] < 0.99
    shares = [r["share_of_total_time"] for r in workload.top_by_total_time]
    assert shares == sorted(shares, reverse=True)


def test_workload_flags_dominant_query_cache_and_temp_spill(workload):
    by_code = {(f.code, f.target) for f in workload.findings}
    assert ("DOMINANT_QUERY", "-4404") in by_code
    assert ("LOW_CACHE_HIT", "-2208") in by_code
    assert ("TEMP_SPILL", "-2208") in by_code
    assert workload.totals["statements_spilling_to_temp"] == 1


def test_n_plus_one_flags_fk_lookup_not_primary_key(workload):
    n1 = {f.target for f in workload.findings if f.code == "N_PLUS_ONE_SUSPECT"}
    assert n1 == {"-5110"}  # refunds by payment_id; payments by id is normal OLTP


def test_in_list_variants_grouped_into_one_fingerprint(workload):
    variants = [f for f in workload.findings if f.code == "QUERY_SHAPE_VARIANTS"]
    assert len(variants) == 1 and variants[0].target == "-1101,-1102,-1103"
    fp = next(r for r in workload.fingerprints if r["variants"] == 3)
    assert fp["calls"] == 120_000 + 95_000 + 40_000


def test_load_statements_csv_and_json(tmp_path):
    rows = sample_statements()
    csv_path = tmp_path / "pgss.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json_path = tmp_path / "pgss.json"
    json_path.write_text(json.dumps({"statements": rows}))
    a, b = load_statements(csv_path), load_statements(json_path)
    assert len(a) == len(b) == len(rows)
    assert a[0].calls == b[0].calls and a[0].cache_hit_ratio == pytest.approx(b[0].cache_hit_ratio)


def test_mysql_digest_rows_are_converted():
    stat = parse_statements(
        [
            {
                "DIGEST": "abc",
                "DIGEST_TEXT": "SELECT * FROM `orders` WHERE `customer_id` = ?",
                "COUNT_STAR": 1000,
                "SUM_TIMER_WAIT": 2_000_000_000_000,  # 2 s in picoseconds
                "SUM_ROWS_SENT": 500,
                "SUM_CREATED_TMP_DISK_TABLES": 3,
            }
        ]
    )[0]
    assert stat.total_exec_time == pytest.approx(2000.0)
    assert stat.mean_exec_time == pytest.approx(2.0)
    assert stat.cache_hit_ratio is None and stat.temp_blks_written == 3


def test_legacy_total_time_column_accepted():
    s = parse_statements([{"queryid": 1, "query": "select 1", "calls": 4, "total_time": 8.0}])[0]
    assert s.mean_exec_time == pytest.approx(2.0)


# --------------------------------------------------------------------------- explain
def test_filter_columns_orders_equality_then_range_and_detects_expressions():
    eq, rng, ex = filter_columns(
        "((p.created_at >= '2026-01-01'::timestamp with time zone) AND (p.merchant_id = 7) "
        "AND ((p.status)::text = 'paid'::text))",
        "p",
    )
    assert eq == ["merchant_id", "status"] and rng == ["created_at"] and ex == []
    assert filter_columns("(lower((customer_email)::text) = 'a'::text)")[2] == ["lower(customer_email)"]
    assert filter_columns("(r.payment_id = p.id)", "r")[0] == ["payment_id"]


def test_seq_scan_on_function_filter_suggests_expression_index(plans):
    rep = analyse_plan(plans["email_lookup"])
    f = next(f for f in rep.findings if f.code == "SEQ_SCAN_SELECTIVE")
    assert f.severity == "high"
    assert (
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_lower_customer_email ON payments (lower(customer_email));"
        in rep.statements
    )
    assert f.evidence["rows_scanned"] == 12_200_000


def test_seq_scan_composite_index_puts_equality_before_range():
    plan = {
        "Plan": {
            "Node Type": "Seq Scan",
            "Relation Name": "payments",
            "Alias": "payments",
            "Filter": "((created_at > '2026-10-01'::timestamp with time zone) AND (merchant_id = 9))",
            "Rows Removed by Filter": 500_000,
            "Plan Rows": 100,
            "Actual Rows": 120,
            "Actual Loops": 1,
            "Actual Total Time": 300.0,
        }
    }
    rep = analyse_plan(plan)
    assert rep.statements == [
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_merchant_id_created_at ON payments (merchant_id, created_at);"
    ]
    assert rep.findings[0].severity == "medium"  # < 1M rows scanned


def test_small_or_unselective_seq_scan_not_flagged():
    base = {
        "Node Type": "Seq Scan",
        "Relation Name": "merchants",
        "Alias": "merchants",
        "Filter": "(country = 'DE'::text)",
    }
    small = {**base, "Rows Removed by Filter": 900, "Actual Rows": 10, "Plan Rows": 10, "Actual Loops": 1}
    unselective = {
        **base,
        "Rows Removed by Filter": 200_000,
        "Actual Rows": 300_000,
        "Plan Rows": 290_000,
        "Actual Loops": 1,
    }
    assert analyse_plan({"Plan": small}).findings == []
    assert analyse_plan({"Plan": unselective}).findings == []


def test_nested_loop_over_seq_scan_is_critical_and_indexes_join_key(plans):
    rep = analyse_plan(plans["refund_join"])
    f = next(f for f in rep.findings if f.code == "NESTED_LOOP_LARGE")
    assert f.severity == "critical" and f.evidence["inner_loops"] == 5_000
    assert (
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refunds_payment_id ON refunds (payment_id);"
        in rep.statements
    )


def test_misestimate_reported_once_at_origin_with_extended_statistics(plans):
    rep = analyse_plan(plans["refund_join"])
    mis = [f for f in rep.findings if f.code == "ROW_MISESTIMATE"]
    assert (
        len(mis) == 1 and mis[0].severity == "high"
    )  # 12 → 5,000 under-estimate on payments, not re-reported on the join
    assert any(
        s.startswith("CREATE STATISTICS IF NOT EXISTS stx_payments_merchant_id_created_at")
        for s in rep.statements
    )


def test_limit_truncation_is_not_a_misestimate(plans):
    rep = analyse_plan(plans["merchant_status"])
    assert "ROW_MISESTIMATE" not in codes(rep.findings)
    f = next(f for f in rep.findings if f.code == "INDEX_FILTER_INEFFICIENT")
    assert "ON payments (merchant_id, status)" in f.remediation


def test_sort_and_hashagg_spills_recommend_work_mem(plans):
    rep = analyse_plan(plans["settlement_report"])
    sort = next(f for f in rep.findings if f.code == "SORT_SPILL")
    assert sort.evidence["suggested_work_mem_mb"] == 1024  # 412 MB on disk × 2.5 → next power of two
    assert "SET LOCAL work_mem" in sort.remediation
    assert "HASH_SPILL" in codes(rep.findings)


def test_lossy_bitmap_and_selective_hash_join(plans):
    assert codes(analyse_plan(plans["bitmap_lossy"]).findings) == ["LOSSY_BITMAP"]
    rep = analyse_plan(plans["ledger_hash_join"])
    assert codes(rep.findings) == ["MISSING_JOIN_INDEX"]
    assert rep.statements == [
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ledger_entries_payment_id ON ledger_entries (payment_id);"
    ]


def test_healthy_plan_has_no_findings_and_hottest_node(plans):
    rep = analyse_plan(plans["healthy"])
    assert rep.findings == [] and rep.statements == []
    assert rep.hottest_nodes[0]["node_type"] == "Index Scan"


def test_explain_accepts_text_and_file_and_rejects_garbage(plans, tmp_path):
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plans["email_lookup"]))
    assert analyse_plan(load_plan(p)).execution_time_ms == pytest.approx(842.9)
    assert analyse_plan(json.dumps(plans["email_lookup"])).node_count == 3
    with pytest.raises(ValueError):
        analyse_plan({"rows": 1})
    with pytest.raises(ValueError):
        analyse_plan([])


def test_hottest_nodes_use_exclusive_time(plans):
    rep = analyse_plan(plans["refund_join"])
    top = rep.hottest_nodes[0]
    assert top["node_type"] == "Nested Loop"  # the join filter, not the cheap children, burns the time
    assert top["exclusive_ms"] > 5_000 and top["share"] > 0.5


# --------------------------------------------------------------------------- indexes
def test_parse_indexdef_variants():
    d = parse_indexdef(
        "CREATE UNIQUE INDEX ux ON public.payments USING btree (merchant_id, created_at DESC) "
        "INCLUDE (amount) WHERE (status = 'paid'::text)"
    )
    assert d.unique and d.table == "payments" and d.columns == ("merchant_id", "created_at DESC")
    assert d.include == ("amount",) and d.predicate.startswith("(status")
    g = parse_indexdef("CREATE INDEX gx ON public.audit_log USING gin (payload jsonb_path_ops)")
    assert g.method == "gin"
    e = parse_indexdef("CREATE INDEX ex ON public.payments USING btree (lower((customer_email)::text))")
    assert e.columns == ("lower((customer_email)::text)",)
    with pytest.raises(ValueError):
        parse_indexdef("not an index")


def test_unused_duplicate_and_redundant_indexes(index_report):
    by = {(f.code, f.target) for f in index_report.findings}
    assert ("UNUSED_INDEX", "idx_payments_legacy_ref") in by
    assert ("DUPLICATE_INDEX", "idx_payments_status_v2") in by
    assert ("DUPLICATE_INDEX", "idx_payments_status") not in by  # exactly one of the pair is dropped
    assert ("REDUNDANT_INDEX", "idx_payments_merchant") in by
    # primary keys / unique constraints are never proposed for dropping
    assert not any(f.target.endswith("_pkey") for f in index_report.findings if "INDEX" in f.code)
    assert index_report.totals["unused_index_bytes"] > 10 * (1 << 30)


def test_fk_without_index_detected_and_covered_fk_ignored(index_report):
    fk = [f for f in index_report.findings if f.code == "FK_WITHOUT_INDEX"]
    assert [f.target for f in fk] == [
        "refunds(payment_id)"
    ]  # payments.merchant_id is covered by a composite prefix
    assert (
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refunds_payment_id ON refunds (payment_id);"
        in index_report.statements
    )


def test_bloat_write_amplification_and_seq_scan_pressure(index_report):
    by = {(f.code, f.target): f for f in index_report.findings}
    bloat = by[("TABLE_BLOAT", "audit_log")]
    assert bloat.severity == "high" and bloat.evidence["last_autovacuum_days"] == pytest.approx(12.2, abs=0.1)
    assert "autovacuum_vacuum_scale_factor = 0.01" in bloat.remediation
    assert ("WRITE_AMPLIFICATION", "ledger_entries") in by
    assert ("SEQ_SCAN_HEAVY", "payments") in by
    health = {t.table: t for t in index_report.tables}
    assert health["ledger_entries"].write_amplification > 5
    assert index_report.tables[0].table == "audit_log"  # sorted by dead ratio


def test_xid_wraparound_severity_bands():
    snap = sample_index_snapshot()
    rep = analyse_indexes(snap)
    xid = next(f for f in rep.findings if f.code == "XID_WRAPAROUND_RISK")
    assert xid.severity == "high" and xid.evidence["pct_of_limit"] == pytest.approx(0.54, abs=0.01)
    critical = copy.deepcopy(snap)
    critical["database"]["datfrozenxid_age"] = 1_700_000_000
    assert (
        next(f for f in analyse_indexes(critical).findings if f.code == "XID_WRAPAROUND_RISK").severity
        == "critical"
    )
    young = copy.deepcopy(snap)
    young["database"]["datfrozenxid_age"] = 90_000_000
    assert "XID_WRAPAROUND_RISK" not in codes(analyse_indexes(young).findings)


def test_autovacuum_settings_scale_with_table_size():
    assert autovacuum_settings(50_000) == {}
    assert autovacuum_settings(5_000_000)["autovacuum_vacuum_scale_factor"] == 0.05
    big = autovacuum_settings(500_000_000, insert_heavy=True)
    assert big["autovacuum_vacuum_scale_factor"] == 0.01
    assert big["autovacuum_vacuum_insert_scale_factor"] == 0.01


# --------------------------------------------------------------------------- capacity
def test_pool_sizing_oversubscription_and_pgbouncer():
    p = pool_sizing(cores=16, app_instances=60, pool_size_per_instance=20, max_connections=1000)
    assert p.optimal_active_connections == 33
    assert p.app_demand == 1200 and p.usable_connections == 997
    assert codes(p.findings)[0] == "CONNECTIONS_OVERSUBSCRIBED"
    assert p.pgbouncer["pool_mode"] == "transaction"
    assert p.server_connections < p.usable_connections
    ok = pool_sizing(cores=8, app_instances=4, pool_size_per_instance=5, max_connections=500)
    assert codes(ok.findings) == ["PGBOUNCER_TRANSACTION_MODE_CAVEATS"]


def test_memory_parameters_self_managed_vs_aurora():
    pg = memory_parameters(ram_gb=64, max_connections=200)
    assert pg["shared_buffers"]["value"] == "16GB" and pg["effective_cache_size"]["value"] == "48GB"
    assert 4 <= pg["work_mem"]["mb"] <= 64
    assert pg["maintenance_work_mem"]["mb"] == 2048  # 5 % of RAM, capped at 2GB
    au = memory_parameters(ram_gb=64, max_connections=200, platform="aurora", workload="olap")
    assert au["shared_buffers"]["value"] == "48GB"
    assert au["shared_buffers"]["parameter_group_unit"] == "8kB pages"
    assert au["work_mem"]["parameter_group_value"] == str(au["work_mem"]["mb"] * 1024)
    with pytest.raises(ValueError):
        memory_parameters(ram_gb=8, max_connections=10, workload="batch")


def test_work_mem_shrinks_as_connections_grow():
    few = memory_parameters(ram_gb=32, max_connections=50, workload="olap")["work_mem"]["mb"]
    many = memory_parameters(ram_gb=32, max_connections=2000, workload="olap")["work_mem"]["mb"]
    assert few > many >= 4


def test_read_scaling_replicas_cache_and_write_bound():
    rep = read_scaling(reads_per_s=20_000, writes_per_s=1_000, lag_tolerance_s=5, primary_cpu_p95=85)
    assert "read-replicas" in rep.strategy and rep.readers >= 1
    cache = read_scaling(
        reads_per_s=5_000, writes_per_s=1_000, lag_tolerance_s=0, primary_cpu_p95=30, hot_key_share=0.4
    )
    assert cache.strategy == ["cache"] and "REPLICA_LAG_INTOLERANT" in codes(cache.findings)
    wb = read_scaling(reads_per_s=500, writes_per_s=4_000, lag_tolerance_s=5, primary_cpu_p95=80)
    assert "WRITE_BOUND" in codes(wb.findings) and wb.readers == 0


def test_partitioning_plan():
    fs = partitioning_plan(sample_capacity_profile()["tables"])
    by = {(f.code, f.target): f for f in fs}
    assert by[("PARTITION_BY_RANGE", "audit_log")].severity == "high"
    assert by[("PARTITION_BY_RANGE", "ledger_entries")].evidence["interval"] == "month"
    assert ("PARTITIONING_NOT_INDICATED", "payments") in by
    assert not any(f.target == "merchants" for f in fs)
    daily = partitioning_plan(
        [
            {
                "name": "events",
                "size_gb": 12_000,
                "timestamp_column": "ts",
                "range_predicate_share": 0.9,
                "growth_gb_per_month": 900,
            }
        ]
    )
    assert daily[0].evidence["interval"] == "day" and "CONSIDER_SHARDING" in codes(daily)


def test_price_table_is_illustrative_and_overridable(tmp_path, monkeypatch):
    table = load_price_table()
    assert table["illustrative"] is True and "db.r7g.2xlarge" in table["instances"]
    custom = tmp_path / "prices.yaml"
    custom.write_text("illustrative: false\ninstances: {db.x.large: {vcpu: 2, memory_gb: 16, hourly: 1.0}}\n")
    monkeypatch.setenv("GOLDEN_DB_PRICING_FILE", str(custom))
    assert load_price_table()["illustrative"] is False
    bad = tmp_path / "bad.yaml"
    bad.write_text("foo: 1\n")
    with pytest.raises(ValueError):
        load_price_table(bad)


def test_rightsize_downsizes_to_graviton_with_io_optimized_savings():
    prof = sample_capacity_profile()
    s = prof["samples"]
    r = rightsize(
        current_class="db.r6i.4xlarge",
        cpu_pct=s["cpu_pct"],
        freeable_memory_gb=s["freeable_memory_gb"],
        read_iops=s["read_iops"],
        write_iops=s["write_iops"],
        storage_gb=2400,
        instance_count=2,
    )
    table = load_price_table()
    assert table["instances"][r.recommended_class]["graviton"] is True
    assert table["instances"][r.recommended_class]["vcpu"] >= r.required_vcpu
    assert r.storage_config == "io-optimized" and r.io_share_of_cost >= 0.25
    assert r.monthly_savings > 0 and r.illustrative_prices is True
    assert {"RIGHTSIZE_INSTANCE", "GRAVITON", "AURORA_IO_OPTIMIZED"} <= set(codes(r.findings))


def test_rightsize_keeps_busy_instance_and_standard_storage():
    r = rightsize(
        current_class="db.r7g.2xlarge",
        cpu_pct=[85.0] * 100,
        freeable_memory_gb=[6.0] * 100,
        read_iops=[500.0] * 100,
        write_iops=[200.0] * 100,
        storage_gb=500,
    )
    assert r.recommended_class != "db.r7g.2xlarge" or r.monthly_savings == 0
    assert load_price_table()["instances"][r.recommended_class]["vcpu"] >= 8  # never shrinks a busy host
    assert r.storage_config == "standard"
    with pytest.raises(KeyError):
        rightsize(
            current_class="db.nope",
            cpu_pct=[1],
            freeable_memory_gb=[1],
            read_iops=[1],
            write_iops=[1],
            storage_gb=1,
        )


def test_low_cache_hit_blocks_memory_downsize():
    s = sample_capacity_profile()["samples"]
    kwargs = dict(
        cpu_pct=s["cpu_pct"],
        freeable_memory_gb=s["freeable_memory_gb"],
        read_iops=s["read_iops"],
        write_iops=s["write_iops"],
        storage_gb=2400,
    )
    r = rightsize(current_class="db.r6i.4xlarge", cache_hit_ratio=0.95, **kwargs)
    assert load_price_table()["instances"][r.recommended_class]["memory_gb"] >= 128


def test_assess_capacity_end_to_end_is_deterministic():
    a = assess_capacity(sample_capacity_profile()).to_dict()
    b = assess_capacity(sample_capacity_profile()).to_dict()
    assert a == b
    assert a["findings"][0]["code"] == "CONNECTIONS_OVERSUBSCRIBED"
    assert a["severity_counts"]["critical"] == 1
    json.dumps(a)  # serialisable for the CLI / API


def test_reports_are_json_serialisable(workload, index_report, plans):
    for doc in (workload.to_dict(), index_report.to_dict(), analyse_plan(plans["refund_join"]).to_dict()):
        assert json.loads(json.dumps(doc))["severity_counts"]


# --------------------------------------------------------------------------- deploy / observability artifacts
def test_database_artifacts_exist_and_parse():
    import yaml

    rules = yaml.safe_load((REPO / "observability/prometheus/rules/database_rules.yml").read_text())
    alerts = {r["alert"] for g in rules["groups"] for r in g["rules"] if "alert" in r}
    assert {
        "PostgresConnectionSaturation",
        "PostgresXIDWraparoundRisk",
        "PostgresReplicationLagHigh",
    } <= alerts
    dash = json.loads((REPO / "observability/grafana/dashboards/golden-database.json").read_text())
    assert dash["uid"] == "golden-database"
    assert all(p["datasource"]["uid"] == "prometheus-golden" for p in dash["panels"] if "datasource" in p)
    tf = (REPO / "deploy/terraform/modules/aws/aurora-postgres/main.tf").read_text()
    assert tf.count('resource "aws_iam_role"') == tf.count(
        "permissions_boundary = var.permissions_boundary_arn"
    )
    assert "pg_stat_statements" in tf
