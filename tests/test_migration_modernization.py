"""Portfolio rationalization (7 Rs / TIME) and database migration assessment."""

from __future__ import annotations

import pytest

from golden.migration import assess_vm, sample_inventory
from golden.migration.assessment import Finding, VMAssessment
from golden.migration.database import (
    CDC_APPLY_GB_PER_HOUR,
    Database,
    assess_database,
    assess_databases,
    cdc_feasibility,
    full_load_hours,
    offline_downtime_minutes,
    recommend_target,
    sample_databases,
)
from golden.migration.portfolio import (
    CSV_COLUMNS,
    DISPOSITIONS,
    Application,
    assess_portfolio,
    decide,
    load_portfolio_csv,
    sample_portfolio,
    time_quadrant,
    write_portfolio_csv,
)


def _blocked(vm: str, app: str, *codes: str) -> VMAssessment:
    return VMAssessment(
        vm=vm,
        application=app,
        criticality="high",
        readiness="blocked",
        complexity=7,
        migration_type="warm",
        estimated_hours=1.0,
        total_disk_gb=100.0,
        findings=[Finding(c, "blocker", c, "fix") for c in codes],
    )


def _ready(vm: str, app: str) -> VMAssessment:
    return VMAssessment(vm, app, "medium", "ready", 1, "cold", 0.5, 80.0, [])


# ----------------------------------------------------------------------------- 7 Rs archetypes
def test_unused_app_is_retired():
    d = decide(Application("old-intranet", users=0, annual_cost=45_000))
    assert d.disposition == "retire" and d.rule == "R1"
    assert d.annual_cost_delta == -45_000 and d.effort == "XS"


def test_retire_candidate_under_legal_hold_is_retained_read_only():
    d = decide(Application("archive", users=0, compliance=["legal-hold"], annual_cost=50_000))
    assert d.disposition == "retain" and d.rule == "R1"
    assert "read-only" in d.target_platform
    assert any("legal-hold" in line for line in d.rationale)


def test_low_value_app_with_dependents_is_not_retired():
    app = Application("shared-lib-svc", users=5, business_value=1, technical_health=2, tech_stack="cobol")
    assert decide(app, dependents=["billing"]).disposition != "retire"
    assert decide(app).disposition == "retire"


def test_cots_with_saas_alternative_is_repurchased():
    d = decide(Application("expenses", users=4000, cots=True, saas_alternative=True, business_value=2))
    assert d.disposition == "repurchase" and d.target_platform == "SaaS"


def test_differentiating_app_with_saas_alternative_is_not_repurchased():
    app = Application(
        "pricing",
        users=100,
        business_value=5,
        saas_alternative=True,
        change_frequency="high",
        tech_stack="go",
    )
    assert decide(app).disposition == "refactor"


def test_mainframe_retained_unless_strategic_and_fast_changing():
    stable = Application("policy", users=900, hosting="mainframe", business_value=5, change_frequency="low")
    hot = Application("claims", users=900, hosting="mainframe", business_value=5, change_frequency="high")
    assert decide(stable).disposition == "retain"
    d = decide(hot)
    assert d.disposition == "refactor"
    assert d.effort == "XL"  # base L + mainframe bump


def test_weblogic_app_replatforms_to_jboss_or_liberty():
    d = decide(Application("claims-portal", users=10, tech_stack="java-weblogic", business_value=3))
    assert d.disposition == "replatform" and d.rule == "R5"
    assert "JBoss EAP" in d.target_platform


def test_dotnet_framework_app_is_rehosted():
    d = decide(Application("billing", users=50, tech_stack="dotnet-framework", db_engine="sqlserver"))
    assert d.disposition == "rehost"
    assert d.target_platform.startswith("OpenShift Virtualization")
    assert any(".NET Framework" in line for line in d.rationale)
    assert "moves with the VM" in d.data_target


def test_stateless_node_app_replatforms_with_managed_db():
    d = decide(Application("quote-api", users=10, tech_stack="node", stateless=True, db_engine="postgresql"))
    assert d.disposition == "replatform"
    assert "Aurora PostgreSQL" in d.data_target


def test_already_cloud_native_or_saas_is_retained():
    native = Application(
        "fraud", users=5, hosting="cloud", stateless=True, twelve_factor=True, containerized=True
    )
    assert decide(native).disposition == "retain"
    assert decide(Application("office", users=10, hosting="saas")).target_platform == "Existing SaaS"


# ----------------------------------------------------------------------------- VM assessment influence
def test_blocked_vm_pushes_stateless_app_to_replatform():
    app = Application("web", users=10, stateless=True, vms=["web-01"])
    d = decide(app, vm_assessments=[_blocked("web-01", "web", "UNSUPPORTED_OS")])
    assert d.disposition == "replatform"
    assert d.rehost_feasible is False and d.blocked_vms == ["web-01"]
    assert any("Rehost blocked" in line for line in d.rationale)


def test_hypervisor_coupled_blockers_on_critical_app_relocate():
    app = Application("erp", business_criticality="high", users=100, tech_stack="sap-ecc", cots=True)
    d = decide(app, vm_assessments=[_blocked("erp-db-01", "erp", "RDM_PHYSICAL", "SHARED_DISK")])
    assert d.disposition == "relocate" and d.rule == "R6"


def test_unrelocatable_blocker_falls_back_to_retain():
    app = Application("gw", business_criticality="high", users=10, tech_stack="cobol-gateway")
    d = decide(app, vm_assessments=[_blocked("gw-01", "gw", "PASSTHROUGH", "UNSUPPORTED_OS")])
    assert d.disposition == "retain" and d.rule == "R8"


def test_ready_vms_mean_rehost_is_feasible():
    app = Application("crm", users=10, tech_stack="dotnet-framework")
    d = decide(app, vm_assessments={"crm-01": _ready("crm-01", "crm")})
    assert d.disposition == "rehost" and d.rehost_feasible is True


def test_sample_portfolio_with_sample_inventory():
    vms = [assess_vm(vm) for vm in sample_inventory()]
    result = assess_portfolio(sample_portfolio(), vms)
    by_app = {a["application"]: a for a in result["applications"]}
    assert 20 <= result["summary"]["applications"] <= 30
    assert all(result["summary"]["dispositions"][d] >= 1 for d in DISPOSITIONS)
    assert by_app["erp"]["disposition"] == "relocate"  # physical RDM on erp-db-01
    assert by_app["legacy-mainframe-gw"]["disposition"] == "retain"  # passthrough + EOL OS
    assert set(result["summary"]["rehost_blocked"]) == {"erp", "legacy-mainframe-gw"}
    assert result["summary"]["estimated_annual_savings"] > 0
    assert result["summary"]["payback_months"] is not None


def test_effort_bumps_and_cost_delta():
    app = Application(
        "pay",
        business_criticality="mission_critical",
        users=10,
        tech_stack="node",
        compliance=["pci-dss"],
        annual_cost=100_000,
    )
    d = decide(app)
    assert d.disposition == "replatform"
    assert d.effort == "XL"  # M + mission critical + regulated
    assert d.annual_cost_delta == -30_000
    assert d.one_time_cost == 500_000


# ----------------------------------------------------------------------------- TIME
@pytest.mark.parametrize(
    ("value", "health", "quadrant"),
    [(5, 5, "invest"), (4, 1, "migrate"), (2, 4, "tolerate"), (1, 1, "eliminate"), (3, 3, "invest")],
)
def test_time_quadrants(value, health, quadrant):
    assert time_quadrant(Application("x", business_value=value, technical_health=health)) == quadrant


# ----------------------------------------------------------------------------- CSV
def test_csv_roundtrip(tmp_path):
    apps = sample_portfolio()
    path = write_portfolio_csv(tmp_path / "portfolio.csv", apps)
    loaded = load_portfolio_csv(path)
    assert [a.to_dict() for a in loaded] == [a.to_dict() for a in apps]


def test_csv_loader_parses_types_and_defaults(tmp_path):
    path = tmp_path / "apps.csv"
    path.write_text(
        "Name,Business_Criticality,Business_Value,Technical_Health,Annual_Cost,Users,Compliance,"
        "SaaS_Alternative,Stateless,VMs\n"
        'crm,Mission Critical,9,0,"$1,200",30,pci;sox,yes,1,crm-01;crm-02\n'
        ",,,,,,,,,\n"
        "tiny,,,,,,,,,\n",
        encoding="utf-8",
    )
    apps = load_portfolio_csv(path)
    assert [a.name for a in apps] == ["crm", "tiny"]
    crm = apps[0]
    assert crm.business_criticality == "mission_critical"
    assert (crm.business_value, crm.technical_health) == (5, 1)  # clamped
    assert crm.annual_cost == 1200.0 and crm.users == 30
    assert crm.compliance == ["pci", "sox"] and crm.vms == ["crm-01", "crm-02"]
    assert crm.saas_alternative and crm.stateless
    assert apps[1].business_value == 3 and apps[1].hosting == "vmware"
    assert "name" in CSV_COLUMNS


# ----------------------------------------------------------------------------- database: math
def test_full_load_time_math():
    # 1000 GB * 8 bits / (1 Gbps * 0.6 * 3600 s) = 3.70 h
    assert full_load_hours(1000, 1.0) == pytest.approx(3.70, abs=0.01)
    assert full_load_hours(1000, 10.0) == pytest.approx(0.37, abs=0.01)
    assert offline_downtime_minutes(1000, 1.0) == pytest.approx(3.7037 * 60 * 2 + 30, abs=0.5)
    with pytest.raises(ValueError):
        full_load_hours(10, 0)


def test_cdc_feasibility_thresholds():
    ok = cdc_feasibility(24, 10)  # 1 GB/h avg, 3 GB/h peak vs 20
    assert ok["feasible"] and ok["lag_risk"] == "low"
    assert ok["backlog_gb_after_full_load"] == 10.0
    assert ok["catchup_hours"] == pytest.approx(10 / (CDC_APPLY_GB_PER_HOUR - 1), abs=0.01)
    high = cdc_feasibility(144, 1)  # 18 GB/h peak = 0.9
    assert high["feasible"] and high["lag_risk"] == "high"
    bad = cdc_feasibility(480, 1)  # 60 GB/h peak
    assert not bad["feasible"] and bad["lag_risk"] == "infeasible"
    assert cdc_feasibility(600, 1)["catchup_hours"] is None  # avg 25 GB/h > apply


# ----------------------------------------------------------------------------- database: strategy
def test_small_database_with_long_window_goes_offline():
    a = assess_database(Database("hr", "mysql", "8.0", 40, 1, max_downtime_minutes=240))
    assert a.strategy == "offline" and a.target == "aurora-mysql"
    assert a.migration_type == "homogeneous" and a.readiness == "ready"
    assert any("dump" in step.lower() for step in a.cutover_plan)


def test_tight_window_homogeneous_postgres_uses_native_replication():
    a = assess_database(Database("quote", "postgresql", "15", 500, 10, max_downtime_minutes=15))
    assert a.strategy == "native_replication"
    assert "logical replication" in a.tool


def test_tight_window_heterogeneous_uses_dms_cdc():
    a = assess_database(
        Database("rep", "oracle", "19c", 1500, 40, plsql_packages=20, max_downtime_minutes=60)
    )
    assert a.target == "aurora-postgresql" and a.migration_type == "heterogeneous"
    assert a.strategy == "full_load_cdc" and "DMS" in a.tool
    assert any("DMS" in step for step in a.cutover_plan)


def test_downtime_budget_and_bandwidth_change_the_strategy():
    db = Database("pg", "postgresql", "14", 300, 5, max_downtime_minutes=120)
    assert assess_database(db, bandwidth_gbps=1.0).strategy == "native_replication"  # ~252 min offline
    assert assess_database(db, bandwidth_gbps=10.0).strategy == "offline"  # ~55 min


def test_high_change_rate_blocks_cdc():
    a = assess_database(Database("click", "mysql", "8.0", 2000, 900, max_downtime_minutes=30))
    assert a.readiness == "blocked"
    assert any(f.code == "CDC_LAG" and f.severity == "blocker" for f in a.findings)
    assert (
        assess_database(
            Database("click", "mysql", "8.0", 2000, 900, max_downtime_minutes=30), apply_gb_per_hour=200
        ).readiness
        != "blocked"
    )


def test_oracle_target_depends_on_plsql_footprint():
    heavy = Database("erp", "oracle", "19c", plsql_packages=400, license="byol")
    light = Database("rep", "oracle", "19c", plsql_packages=10)
    assert recommend_target(heavy)[0] == "rds-oracle"
    assert any("BYOL" in line for line in recommend_target(heavy)[1])
    assert recommend_target(light)[0] == "aurora-postgresql"
    assert recommend_target(light, prefer="homogeneous")[0] == "rds-oracle"


def test_sqlserver_targets_and_babelfish():
    assert recommend_target(Database("a", "sqlserver", clr=True))[0] == "rds-sqlserver"
    target, why = recommend_target(Database("b", "sqlserver", stored_procedures=40))
    assert target == "aurora-postgresql" and any("Babelfish" in w for w in why)
    a = assess_database(Database("b", "sqlserver", "2019", 50, 1, clr=True), prefer="heterogeneous")
    assert any(f.code == "CLR" and f.severity == "blocker" for f in a.findings)


def test_postgres_on_openshift_targets_crunchy():
    assert recommend_target(Database("p", "postgresql"), platform="openshift")[0] == "crunchy-postgres"
    with pytest.raises(ValueError):
        recommend_target(Database("x", "informix"))


def test_compatibility_findings_and_conversion_effort():
    a = assess_database(
        Database(
            "claims",
            "oracle",
            "11.2",
            900,
            60,
            stored_procedures=60,
            plsql_packages=12,
            triggers=40,
            lobs=True,
            tables_without_pk=14,
            max_downtime_minutes=60,
        )
    )
    codes = {f.code for f in a.findings}
    assert {"PLSQL_PACKAGES", "STORED_PROCEDURES", "TRIGGERS", "LOBS", "NO_PRIMARY_KEY"} <= codes
    assert a.conversion["tool"] == "AWS SCT"
    assert sum(a.conversion["actions"].values()) == 60 + 12 + 40
    assert a.conversion["hours"] > 0
    homo = assess_database(Database("h", "mysql", "8.0", 10, 1))
    assert homo.conversion["hours"] == 0.0


def test_huge_database_over_slow_link_flags_long_full_load():
    a = assess_database(Database("dw", "postgresql", "14", 40_000, 10, max_downtime_minutes=60))
    assert any(f.code == "LONG_FULL_LOAD" for f in a.findings)


def test_sample_databases_summary():
    result = assess_databases(sample_databases())
    s = result["summary"]
    assert s["databases"] == len(sample_databases())
    assert set(s["by_strategy"]) == {"offline", "full_load_cdc", "native_replication"}
    assert s["heterogeneous"] >= 2 and s["conversion_hours"] > 0
    assert "clickstream-mysql" in s["blocked"]
    assert all(d["cutover_plan"] for d in result["databases"])
