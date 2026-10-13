"""Database migration assessment: target, compatibility, strategy, timing and cutover plan.

For each source database the assessment answers:

1. **Target** — homogeneous (same engine, managed) or heterogeneous (engine change), e.g. Oracle →
   Amazon RDS for Oracle (BYOL) or Aurora PostgreSQL; SQL Server → RDS for SQL Server or Aurora
   PostgreSQL with Babelfish; MySQL → Aurora MySQL; PostgreSQL → Aurora PostgreSQL or Crunchy
   Postgres for Kubernetes on OpenShift.
2. **Compatibility findings** — ``Finding(code, severity, message, remediation)`` as in the VM
   assessment, plus a schema-conversion estimate (AWS SCT action items bucketed simple / medium /
   complex) for heterogeneous moves.
3. **Strategy** — ``offline`` (dump / restore), ``full_load_cdc`` (AWS DMS full load + change data
   capture) or ``native_replication`` (logical replication, binlog replication, ...), chosen from size,
   change rate and the downtime budget.
4. **Timing** — full-load hours from size and bandwidth, offline downtime, CDC apply headroom and
   catch-up time.
5. **Cutover plan** — ordered steps for the chosen strategy.

All throughput and per-object effort figures are planning heuristics exposed as module constants; replace
them with measurements from a rehearsal (DMS task statistics, SCT assessment report) as soon as you have them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from golden.migration.assessment import Finding

ENGINES = ("oracle", "sqlserver", "mysql", "mariadb", "postgresql", "db2")

# --- planning heuristics ----------------------------------------------------------------------------
LINK_EFFICIENCY = 0.6  # usable fraction of the network link for bulk copy (same as VM transfers)
OFFLINE_FACTOR = 2.0  # dump + transfer + restore + index rebuild ≈ 2× raw transfer time
OFFLINE_FIXED_MINUTES = 30  # validation + DNS / connection-string switch
CDC_PEAK_FACTOR = 3.0  # peak-hour change rate vs. the daily average
CDC_APPLY_GB_PER_HOUR = 20.0  # default sustained apply rate of one DMS task / replication stream
CDC_SAFE_UTILIZATION = 0.7  # above this, lag grows during peaks
LONG_FULL_LOAD_HOURS = 72.0
# Fraction of objects per SCT action-item complexity bucket, and hours per bucket.
SCT_MIX = {
    "stored_procedures": (0.6, 0.3, 0.1),
    "plsql_packages": (0.2, 0.5, 0.3),
    "triggers": (0.7, 0.25, 0.05),
}
SCT_HOURS = {"simple": 0.5, "medium": 2.0, "complex": 8.0}
# Oldest source versions assumed for DMS CDC; verify against the current DMS source-endpoint docs.
MIN_CDC_VERSION = {"oracle": 11, "sqlserver": 2012, "mysql": 5, "mariadb": 10, "postgresql": 10, "db2": 10}

# Native replication paths into the recommended managed / platform targets.
NATIVE_REPLICATION = {
    ("postgresql", "aurora-postgresql"): "PostgreSQL logical replication (publication → subscription)",
    ("postgresql", "crunchy-postgres"): "PostgreSQL logical replication into Crunchy Postgres (PGO)",
    ("mysql", "aurora-mysql"): "MySQL binlog replication into Aurora MySQL",
    ("mariadb", "aurora-mysql"): "MariaDB binlog replication into Aurora MySQL (verify GTID compatibility)",
    ("sqlserver", "rds-sqlserver"): "Native backup/restore via S3 with differential + log restores",
}
OFFLINE_TOOLS = {
    "oracle": "Data Pump (expdp/impdp) via S3 / DBMS_FILE_TRANSFER",
    "sqlserver": "Native .bak backup to S3 → rds_restore_database",
    "mysql": "mydumper/myloader (or mysqldump)",
    "mariadb": "mydumper/myloader (or mysqldump)",
    "postgresql": "pg_dump -Fd -j / pg_restore -j",
    "db2": "db2move / export + SCT-converted DDL load",
}
TARGET_LABELS = {
    "rds-oracle": "Amazon RDS for Oracle (BYOL)",
    "rds-sqlserver": "Amazon RDS for SQL Server",
    "aurora-postgresql": "Amazon Aurora PostgreSQL",
    "aurora-mysql": "Amazon Aurora MySQL",
    "crunchy-postgres": "Crunchy Postgres for Kubernetes on OpenShift",
}


@dataclass
class Database:
    name: str
    engine: str  # oracle | sqlserver | mysql | mariadb | postgresql | db2
    version: str = ""
    size_gb: float = 0.0
    change_rate_gb_day: float = 0.0  # redo / binlog / WAL volume of row changes per day
    application: str = ""
    edition: str = ""  # enterprise | standard | ...
    stored_procedures: int = 0
    plsql_packages: int = 0
    triggers: int = 0
    linked_servers: bool = False  # SQL Server linked servers / Oracle DB links
    clr: bool = False  # SQL Server CLR assemblies
    partitioning: bool = False
    lobs: bool = False
    replication: bool = False  # existing replication / CDC on the source
    rac: bool = False
    tde: bool = False
    tables_without_pk: int = 0
    max_downtime_minutes: int = 240
    license: str = ""  # byol | license-included | open-source

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Database:
        return cls(**data)

    @property
    def major_version(self) -> int:
        digits = ""
        for ch in self.version:
            if ch.isdigit():
                digits += ch
            elif digits:
                break
        return int(digits) if digits else 0


@dataclass
class DatabaseAssessment:
    database: str
    application: str
    engine: str
    target: str  # key of TARGET_LABELS
    target_label: str
    migration_type: str  # homogeneous | heterogeneous
    strategy: str  # offline | full_load_cdc | native_replication
    tool: str
    full_load_hours: float
    offline_downtime_minutes: float
    cdc: dict[str, Any]
    conversion: dict[str, Any]
    readiness: str  # ready | needs_remediation | blocked
    rationale: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    cutover_plan: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ----------------------------------------------------------------------------- math
def full_load_hours(size_gb: float, bandwidth_gbps: float, efficiency: float = LINK_EFFICIENCY) -> float:
    """Hours to copy ``size_gb`` over a ``bandwidth_gbps`` link at ``efficiency`` utilization."""
    if bandwidth_gbps <= 0 or efficiency <= 0:
        raise ValueError("bandwidth_gbps and efficiency must be positive")
    return round(size_gb * 8 / (bandwidth_gbps * efficiency * 3600), 2)


def offline_downtime_minutes(size_gb: float, bandwidth_gbps: float) -> float:
    return round(full_load_hours(size_gb, bandwidth_gbps) * 60 * OFFLINE_FACTOR + OFFLINE_FIXED_MINUTES, 1)


def cdc_feasibility(
    change_rate_gb_day: float,
    full_load_hours_: float,
    apply_gb_per_hour: float = CDC_APPLY_GB_PER_HOUR,
) -> dict[str, Any]:
    """Can ongoing replication keep up? Compares the peak-hour change rate with the apply rate.

    ``catchup_hours`` is the time to drain changes accumulated during the full load at the average
    change rate (``None`` if apply cannot outrun the average rate).
    """
    avg = change_rate_gb_day / 24
    peak = avg * CDC_PEAK_FACTOR
    utilization = peak / apply_gb_per_hour if apply_gb_per_hour > 0 else float("inf")
    backlog = avg * full_load_hours_
    headroom = apply_gb_per_hour - avg
    return {
        "avg_gb_per_hour": round(avg, 2),
        "peak_gb_per_hour": round(peak, 2),
        "apply_gb_per_hour": apply_gb_per_hour,
        "peak_utilization": round(utilization, 2),
        "feasible": utilization <= 1.0,
        "lag_risk": "low"
        if utilization <= CDC_SAFE_UTILIZATION
        else ("high" if utilization <= 1 else "infeasible"),
        "backlog_gb_after_full_load": round(backlog, 1),
        "catchup_hours": round(backlog / headroom, 2) if headroom > 0 else None,
    }


# ----------------------------------------------------------------------------- target selection
def recommend_target(db: Database, *, platform: str = "aws", prefer: str = "auto") -> tuple[str, list[str]]:
    """Return (target key, rationale). ``platform`` is aws | openshift; ``prefer`` auto | homogeneous | heterogeneous."""
    e = db.engine.lower()
    why: list[str] = []
    if e == "oracle":
        heavy = db.plsql_packages > 100 or db.rac or (db.edition.lower() == "enterprise" and db.partitioning)
        if prefer == "homogeneous" or (prefer == "auto" and heavy):
            why.append(
                f"Oracle with {db.plsql_packages} PL/SQL packages"
                + (", RAC" if db.rac else "")
                + (", partitioning" if db.partitioning else "")
                + ": stay on Oracle to avoid a large conversion"
            )
            if db.license.lower() == "byol":
                why.append("BYOL licences carry over to RDS for Oracle")
            return "rds-oracle", why
        why.append(
            f"Oracle with modest PL/SQL ({db.plsql_packages} packages, {db.stored_procedures} procedures): "
            "convert to Aurora PostgreSQL to drop Oracle licences"
        )
        return "aurora-postgresql", why
    if e == "sqlserver":
        sticky = db.clr or db.linked_servers or db.stored_procedures > 200
        if prefer == "homogeneous" or (prefer == "auto" and sticky):
            parts = [p for p, on in (("CLR", db.clr), ("linked servers", db.linked_servers)) if on]
            if db.stored_procedures > 200:
                parts.append(f"{db.stored_procedures} stored procedures")
            why.append(f"SQL Server with {', '.join(parts) or 'homogeneous preference'}: RDS for SQL Server")
            return "rds-sqlserver", why
        why.append(
            "SQL Server without CLR/linked servers: Aurora PostgreSQL; Babelfish can keep T-SQL and the TDS "
            "wire protocol for most of the app (run the Babelfish Compass report first)"
        )
        return "aurora-postgresql", why
    if e in {"mysql", "mariadb"}:
        why.append(f"{e} → Aurora MySQL (homogeneous, MySQL-compatible)")
        return "aurora-mysql", why
    if e == "postgresql":
        if platform == "openshift":
            why.append("PostgreSQL on the OpenShift platform: Crunchy Postgres for Kubernetes (PGO)")
            return "crunchy-postgres", why
        why.append("PostgreSQL → Aurora PostgreSQL (homogeneous)")
        return "aurora-postgresql", why
    if e == "db2":
        why.append("Db2 → Aurora PostgreSQL (heterogeneous, SCT supports Db2 LUW sources)")
        return "aurora-postgresql", why
    raise ValueError(f"unsupported engine '{db.engine}' (expected one of {', '.join(ENGINES)})")


def _target_engine(target: str) -> str:
    return {
        "rds-oracle": "oracle",
        "rds-sqlserver": "sqlserver",
        "aurora-postgresql": "postgresql",
        "crunchy-postgres": "postgresql",
        "aurora-mysql": "mysql",
    }[target]


def _homogeneous(engine: str, target: str) -> bool:
    t = _target_engine(target)
    return engine == t or (engine == "mariadb" and t == "mysql")


# ----------------------------------------------------------------------------- findings
def _conversion(db: Database, heterogeneous: bool) -> dict[str, Any]:
    if not heterogeneous:
        return {
            "tool": "none (homogeneous)",
            "actions": {"simple": 0, "medium": 0, "complex": 0},
            "hours": 0.0,
        }
    actions = {"simple": 0.0, "medium": 0.0, "complex": 0.0}
    for attr, mix in SCT_MIX.items():
        n = getattr(db, attr)
        for bucket, share in zip(("simple", "medium", "complex"), mix, strict=True):
            actions[bucket] += n * share
    counts = {k: round(v) for k, v in actions.items()}
    hours = sum(counts[k] * SCT_HOURS[k] for k in counts)
    tool = "AWS SCT (+ Babelfish Compass)" if db.engine == "sqlserver" else "AWS SCT"
    return {"tool": tool, "actions": counts, "hours": round(hours, 1)}


def _findings(db: Database, target: str, heterogeneous: bool, conv: dict[str, Any]) -> list[Finding]:
    f: list[Finding] = []
    e = db.engine.lower()
    if heterogeneous and db.plsql_packages:
        f.append(
            Finding(
                "PLSQL_PACKAGES",
                "warning" if db.plsql_packages <= 100 else "blocker",
                f"{db.plsql_packages} PL/SQL packages need conversion to PL/pgSQL",
                "Run the SCT assessment report; package state/globals and autonomous transactions need redesign "
                "(consider the homogeneous RDS for Oracle target if > 100 packages)",
            )
        )
    if heterogeneous and db.stored_procedures:
        f.append(
            Finding(
                "STORED_PROCEDURES",
                "warning" if db.stored_procedures > 50 else "info",
                f"{db.stored_procedures} stored procedures to convert",
                f"Estimated {conv['hours']} h of SCT action items ({conv['actions']}); unit-test converted code",
            )
        )
    if heterogeneous and db.triggers:
        f.append(
            Finding(
                "TRIGGERS",
                "info",
                f"{db.triggers} triggers",
                "Convert with SCT and disable on the target during full load to avoid double-firing",
            )
        )
    if db.linked_servers:
        f.append(
            Finding(
                "LINKED_SERVERS",
                "warning",
                "Linked servers / database links in use",
                "Inventory remote queries; replace with APIs or postgres_fdw/dblink, or keep a homogeneous target "
                "and verify which link types the managed service supports",
            )
        )
    if db.clr:
        f.append(
            Finding(
                "CLR",
                "blocker" if target != "rds-sqlserver" else "warning",
                "SQL CLR assemblies in use",
                "Babelfish/PostgreSQL cannot run CLR; RDS for SQL Server support for CLR depends on version — "
                "verify, otherwise move logic to the application tier or use SQL Server on EC2",
            )
        )
    if db.rac:
        f.append(
            Finding(
                "RAC",
                "warning",
                "Oracle RAC on the source",
                "Managed targets use Multi-AZ instead of RAC; validate connection failover (FAN/TAF) in the app",
            )
        )
    if db.partitioning and heterogeneous:
        f.append(
            Finding(
                "PARTITIONING",
                "info",
                "Table partitioning",
                "Map to PostgreSQL declarative partitioning; reference/interval partitions need manual DDL",
            )
        )
    if db.lobs:
        f.append(
            Finding(
                "LOBS",
                "warning",
                "LOB columns",
                "Use DMS limited-LOB mode with a measured max LOB size; tables with larger LOBs go in a separate "
                "full-LOB / inline-LOB task",
            )
        )
    if db.replication:
        f.append(
            Finding(
                "SOURCE_REPLICATION",
                "info",
                "Source already runs replication / CDC",
                "Check log retention and supplemental logging do not conflict; capture from a standby where supported",
            )
        )
    if db.tables_without_pk:
        f.append(
            Finding(
                "NO_PRIMARY_KEY",
                "warning",
                f"{db.tables_without_pk} tables without a primary key",
                "CDC updates/deletes need a PK or unique key (or full supplemental logging); add keys before CDC",
            )
        )
    if db.tde:
        f.append(
            Finding(
                "TDE",
                "info",
                "Transparent Data Encryption on the source",
                "Grant the CDC user access to encrypted redo/logs; target encryption via KMS",
            )
        )
    floor = MIN_CDC_VERSION.get(e)
    if floor and db.major_version and db.major_version < floor:
        f.append(
            Finding(
                "OLD_VERSION",
                "warning",
                f"{e} {db.version} is older than the assumed CDC minimum ({floor})",
                "Upgrade the source first or plan an offline migration; verify against current DMS docs",
            )
        )
    return f


# ----------------------------------------------------------------------------- strategy
def _cutover_plan(strategy: str, db: Database, target_label: str, heterogeneous: bool) -> list[str]:
    pre = [
        f"Provision {target_label} (encryption, parameter group, backups, monitoring)",
    ]
    if heterogeneous:
        pre.append(
            "Convert and apply schema with SCT; fix action items; create indexes/constraints after load"
        )
    validate = "Validate: row counts per table, checksums on key tables, sample queries, app smoke tests"
    if strategy == "offline":
        return pre + [
            "Rehearse dump/restore end to end and record the timing",
            "Stop application writes (maintenance page); confirm no open transactions",
            f"Dump the source with {OFFLINE_TOOLS.get(db.engine, 'native tools')}",
            "Transfer and restore on the target; rebuild indexes and gather statistics",
            validate,
            "Switch connection strings / DNS; re-enable writes; keep the source read-only for rollback",
        ]
    if strategy == "native_replication":
        return pre + [
            "Seed the target (snapshot/backup restore) and start native replication",
            "Monitor replication lag until steady below the cutover threshold",
            validate + " (while replicating)",
            "Stop application writes; wait for lag = 0; promote/stop replication on the target",
            "Reset sequences/identities; switch connection strings / DNS; re-enable writes",
            "Keep reverse replication or the read-only source for the rollback window",
        ]
    return pre + [
        "Enable CDC prerequisites (supplemental logging / binlog ROW / logical decoding, log retention)",
        "Start the DMS full-load-and-cdc task; disable target triggers and FKs during full load",
        "Run DMS data validation; fix table errors; monitor CDCLatencySource/Target alarms",
        validate + " (while CDC runs)",
        "Stop application writes; wait for CDC latency ≈ 0; stop the task",
        "Re-enable triggers/FKs, reset sequences; switch connection strings / DNS; re-enable writes",
        "Keep the source read-only (or a reverse CDC task) for the rollback window",
    ]


def assess_database(
    db: Database,
    *,
    bandwidth_gbps: float = 1.0,
    platform: str = "aws",
    prefer: str = "auto",
    apply_gb_per_hour: float = CDC_APPLY_GB_PER_HOUR,
) -> DatabaseAssessment:
    engine = db.engine.lower()
    target, why = recommend_target(db, platform=platform, prefer=prefer)
    heterogeneous = not _homogeneous(engine, target)
    conv = _conversion(db, heterogeneous)
    findings = _findings(db, target, heterogeneous, conv)

    load_h = full_load_hours(db.size_gb, bandwidth_gbps)
    offline_min = offline_downtime_minutes(db.size_gb, bandwidth_gbps)
    cdc = cdc_feasibility(db.change_rate_gb_day, load_h, apply_gb_per_hour)

    native = NATIVE_REPLICATION.get((engine, target))
    if offline_min <= db.max_downtime_minutes:
        strategy, tool = "offline", OFFLINE_TOOLS.get(engine, "native dump/restore")
        why.append(
            f"Offline dump/restore fits the downtime budget ({offline_min:.0f} ≤ {db.max_downtime_minutes} min)"
        )
    elif native and not heterogeneous:
        strategy, tool = "native_replication", native
        why.append(
            f"Offline needs ~{offline_min:.0f} min > {db.max_downtime_minutes} min budget; homogeneous move "
            f"with a native path: {native}"
        )
    else:
        strategy, tool = "full_load_cdc", "AWS DMS full-load-and-cdc"
        why.append(
            f"Offline needs ~{offline_min:.0f} min > {db.max_downtime_minutes} min budget; "
            + ("heterogeneous target" if heterogeneous else "no native replication path to the target")
            + " → DMS full load + CDC"
        )

    if strategy != "offline":
        if not cdc["feasible"]:
            findings.append(
                Finding(
                    "CDC_LAG",
                    "blocker",
                    f"Peak change rate {cdc['peak_gb_per_hour']} GB/h exceeds apply rate {apply_gb_per_hour} GB/h",
                    "Split into parallel tasks by table set, enable batch apply, scale the replication instance, "
                    "or reduce change volume (purge jobs) during migration",
                )
            )
        elif cdc["lag_risk"] == "high":
            findings.append(
                Finding(
                    "CDC_LAG",
                    "warning",
                    f"Peak change rate uses {cdc['peak_utilization']:.0%} of the apply rate",
                    "Expect lag during peaks; schedule cutover off-peak and consider parallel apply",
                )
            )
    if load_h > LONG_FULL_LOAD_HOURS:
        findings.append(
            Finding(
                "LONG_FULL_LOAD",
                "warning",
                f"Full load takes ~{load_h:.0f} h at {bandwidth_gbps} Gbps",
                "Increase bandwidth (Direct Connect), parallelize by table/partition, or seed offline "
                "(AWS Snowball / backup restore) and apply CDC from the seed point",
            )
        )

    blockers = sum(1 for x in findings if x.severity == "blocker")
    warnings = sum(1 for x in findings if x.severity == "warning")
    readiness = "blocked" if blockers else ("needs_remediation" if warnings else "ready")
    label = TARGET_LABELS[target]
    return DatabaseAssessment(
        database=db.name,
        application=db.application or "unassigned",
        engine=engine,
        target=target,
        target_label=label,
        migration_type="heterogeneous" if heterogeneous else "homogeneous",
        strategy=strategy,
        tool=tool,
        full_load_hours=load_h,
        offline_downtime_minutes=offline_min,
        cdc=cdc,
        conversion=conv,
        readiness=readiness,
        rationale=why,
        findings=findings,
        cutover_plan=_cutover_plan(strategy, db, label, heterogeneous),
    )


def assess_databases(
    dbs: Iterable[Database],
    *,
    bandwidth_gbps: float = 1.0,
    platform: str = "aws",
    apply_gb_per_hour: float = CDC_APPLY_GB_PER_HOUR,
) -> dict[str, Any]:
    dbs = list(dbs)
    results = [
        assess_database(
            d, bandwidth_gbps=bandwidth_gbps, platform=platform, apply_gb_per_hour=apply_gb_per_hour
        )
        for d in dbs
    ]
    return {
        "summary": {
            "databases": len(results),
            "total_size_tb": round(sum(d.size_gb for d in dbs) / 1024, 2),
            "by_strategy": dict(sorted(Counter(r.strategy for r in results).items())),
            "by_target": dict(sorted(Counter(r.target for r in results).items())),
            "heterogeneous": sum(1 for r in results if r.migration_type == "heterogeneous"),
            "conversion_hours": round(sum(r.conversion["hours"] for r in results), 1),
            "blocked": sorted(r.database for r in results if r.readiness == "blocked"),
            "top_issues": Counter(
                f.code for r in results for f in r.findings if f.severity != "info"
            ).most_common(5),
        },
        "databases": [r.to_dict() for r in results],
    }


# ----------------------------------------------------------------------------- samples
def sample_databases() -> list[Database]:
    """Representative estate: one database per common migration pattern."""
    return [
        Database("erp-ora", "oracle", "19c", 3200, 120, "erp", "enterprise", stored_procedures=900,
                 plsql_packages=420, triggers=300, partitioning=True, lobs=True, rac=True, tde=True,
                 max_downtime_minutes=120, license="byol"),
        Database("reporting-ora", "oracle", "12.2", 1500, 40, "reporting", "enterprise", stored_procedures=120,
                 plsql_packages=35, triggers=20, lobs=True, max_downtime_minutes=480, license="byol"),
        Database("claims-ora", "oracle", "11.2", 900, 60, "claims-portal", "standard", stored_procedures=60,
                 plsql_packages=12, triggers=40, tables_without_pk=14, max_downtime_minutes=60,
                 license="license-included"),
        Database("crm-sql", "sqlserver", "2016", 400, 25, "crm", "standard", stored_procedures=340,
                 triggers=30, linked_servers=True, max_downtime_minutes=60, license="license-included"),
        Database("billing-sql", "sqlserver", "2019", 650, 30, "billing-engine", "enterprise",
                 stored_procedures=150, clr=True, max_downtime_minutes=30, license="license-included"),
        Database("dealer-sql", "sqlserver", "2014", 80, 2, "dealer-extranet", "standard", stored_procedures=45,
                 max_downtime_minutes=240, license="license-included"),
        Database("payments-pg", "postgresql", "13", 800, 130, "payments", stored_procedures=40,
                 replication=True, max_downtime_minutes=5, license="open-source"),
        Database("quote-pg", "postgresql", "15", 120, 10, "quote-api", max_downtime_minutes=15,
                 license="open-source"),
        Database("hr-mysql", "mysql", "5.7", 40, 1, "hr-portal", max_downtime_minutes=240,
                 license="open-source"),
        Database("clickstream-mysql", "mysql", "8.0", 2000, 900, "customer-mobile-bff", lobs=True,
                 max_downtime_minutes=30, license="open-source"),
    ]  # fmt: skip
