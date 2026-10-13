"""Capacity and cost planning for PostgreSQL / Aurora PostgreSQL.

Pure functions, each returning the numbers *and* the reasoning:

* :func:`pool_sizing` — active connections ≈ ``cores × 2 + effective_spindles`` (the PostgreSQL wiki
  heuristic); app demand (instances × pool) vs ``max_connections``; PgBouncer transaction pooling.
* :func:`memory_parameters` — shared_buffers, effective_cache_size, work_mem, maintenance_work_mem from
  instance RAM and max_connections (with Aurora / RDS differences).
* :func:`read_scaling` — read replicas vs cache from read/write ratio, lag tolerance and hot-key share.
* :func:`partitioning_plan` — monthly (or daily) declarative range partitioning for large time-series tables.
* :func:`rightsize` — RDS/Aurora instance class from p95 CPU / freeable memory with headroom, Graviton
  preference, Aurora I/O-Optimized vs Standard break-even; dollar figures come from a price table passed
  in (default: the *illustrative* ``pricing.yaml`` shipped with this package — never live prices).

MySQL notes: InnoDB's equivalent of shared_buffers is ``innodb_buffer_pool_size`` (~70-75 % of RAM on a
dedicated host because InnoDB bypasses the OS cache with O_DIRECT); per-session ``sort_buffer_size`` /
``join_buffer_size`` play work_mem's role; ProxySQL / RDS Proxy replace PgBouncer.
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from golden.database.findings import Finding, severity_counts, sort_findings

HOURS_PER_MONTH = 730


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * pct / 100
    lo, hi = math.floor(k), math.ceil(k)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def load_price_table(path: str | Path | None = None) -> dict[str, Any]:
    """Load the price table: explicit path → ``GOLDEN_DB_PRICING_FILE`` → bundled illustrative table."""
    src = path or os.getenv("GOLDEN_DB_PRICING_FILE", "")
    text = (
        Path(src).read_text("utf-8")
        if src
        else resources.files("golden.database").joinpath("pricing.yaml").read_text("utf-8")
    )
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or "instances" not in data:
        raise ValueError("price table must be a mapping with an 'instances' section")
    return data


# --------------------------------------------------------------------------- connection pooling
@dataclass
class PoolSizing:
    optimal_active_connections: int
    app_demand: int
    usable_connections: int
    utilisation: float
    pgbouncer: dict[str, int | str]
    server_connections: int
    direct_pool_per_instance: int
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d


def pool_sizing(
    *,
    cores: int,
    app_instances: int,
    pool_size_per_instance: int,
    max_connections: int,
    effective_spindles: int = 1,
    reserved_connections: int = 3,
    pgbouncer_replicas: int = 2,
) -> PoolSizing:
    """Size the server-side pool. More concurrent *active* connections than ``cores × 2 + spindles``
    adds context switching and lock contention, not throughput; idle connections still cost ~5-10 MB each.
    On SSD/EBS, ``effective_spindles`` is a tuning knob (1 for a cache-resident working set)."""
    optimal = cores * 2 + effective_spindles
    demand = app_instances * pool_size_per_instance
    usable = max(1, max_connections - reserved_connections)
    findings: list[Finding] = []
    per_bouncer = max(1, math.ceil(optimal / max(pgbouncer_replicas, 1)))
    reserve = max(1, per_bouncer // 4)
    server_connections = (per_bouncer + reserve) * pgbouncer_replicas
    bouncer: dict[str, int | str] = {
        "pool_mode": "transaction",
        "replicas": pgbouncer_replicas,
        "default_pool_size": per_bouncer,
        "reserve_pool_size": reserve,
        "max_client_conn": int(math.ceil(demand * 1.2 / max(pgbouncer_replicas, 1))),
        "max_db_connections": per_bouncer + reserve,
    }
    direct = max(2, optimal // max(app_instances, 1))
    if demand > usable:
        findings.append(
            Finding(
                "CONNECTIONS_OVERSUBSCRIBED",
                "critical",
                f"{app_instances} app instances × pool {pool_size_per_instance} = {demand} connections exceed "
                f"{usable} usable (max_connections {max_connections} − {reserved_connections} reserved)",
                "Scale-out or a deploy surge will fail with 'too many clients'. Put PgBouncer (transaction mode) or "
                f"RDS Proxy in front: {server_connections} server connections can serve "
                f"{demand} clients. Do not raise max_connections to paper over it.",
                "connections",
                {"demand": demand, "usable": usable},
            )
        )
    elif demand > optimal * 4:
        findings.append(
            Finding(
                "CONNECTIONS_OVERPROVISIONED",
                "medium",
                f"Client pools allow {demand} connections; the server does useful work with ~{optimal} active",
                f"Shrink per-instance pools to ~{direct} or pool centrally with PgBouncer (transaction mode).",
                "connections",
                {"demand": demand, "optimal_active": optimal},
            )
        )
    findings.append(
        Finding(
            "PGBOUNCER_TRANSACTION_MODE_CAVEATS",
            "info",
            "Transaction pooling breaks session state",
            "No session-level SET / advisory locks / LISTEN / WITH HOLD cursors across transactions; use "
            "SET LOCAL; protocol-level prepared statements need PgBouncer ≥ 1.21 with max_prepared_statements.",
            "pgbouncer",
        )
    )
    return PoolSizing(
        optimal_active_connections=optimal,
        app_demand=demand,
        usable_connections=usable,
        utilisation=round(demand / usable, 3),
        pgbouncer=bouncer,
        server_connections=server_connections,
        direct_pool_per_instance=direct,
        findings=findings,
    )


# --------------------------------------------------------------------------- memory parameters
def _mb(value: float) -> str:
    return f"{int(value) // 1024}GB" if value >= 1024 and int(value) % 1024 == 0 else f"{int(value)}MB"


def memory_parameters(
    *,
    ram_gb: float,
    max_connections: int,
    workload: str = "oltp",
    platform: str = "self-managed",
    parallel_ops_per_query: int = 2,
    safety_factor: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Recommended memory GUCs with the formula used for each.

    ``work_mem`` is per sort/hash *node* per connection, so the budget is
    ``(RAM − shared_buffers) × safety / (max_connections × ops_per_query)``, clamped to a sane range.
    ``platform="aurora"``: Aurora has no double buffering through an OS page cache for data files, so its
    default shared_buffers is ~75 % of RAM — keep that; tune work_mem in the parameter group.
    """
    if workload not in {"oltp", "olap", "mixed"}:
        raise ValueError("workload must be oltp, olap or mixed")
    ram_mb = ram_gb * 1024
    sb_frac = 0.75 if platform == "aurora" else 0.25
    shared_buffers = ram_mb * sb_frac
    ecs = ram_mb * 0.75
    available = (ram_mb - (shared_buffers if platform != "aurora" else ram_mb * 0.25)) * safety_factor
    work_mem = available / max(max_connections * parallel_ops_per_query, 1)
    cap = {"oltp": 64, "mixed": 256, "olap": 1024}[workload]
    work_mem = int(min(max(work_mem, 4), cap))
    mwm = int(min(2048, max(64, ram_mb * 0.05)))
    out: dict[str, dict[str, Any]] = {
        "shared_buffers": {
            "value": _mb(shared_buffers),
            "mb": int(shared_buffers),
            "rationale": (
                "Aurora default {DBInstanceClassMemory*3/4}; storage layer has no OS-cache double buffering"
                if platform == "aurora"
                else "25 % of RAM; the OS page cache holds the rest (PostgreSQL double-buffers)"
            ),
        },
        "effective_cache_size": {
            "value": _mb(ecs),
            "mb": int(ecs),
            "rationale": "75 % of RAM: planner hint for shared_buffers + OS cache, allocates nothing",
        },
        "work_mem": {
            "value": _mb(work_mem),
            "mb": work_mem,
            "rationale": f"(RAM − shared_buffers) × {safety_factor} / (max_connections {max_connections} × "
            f"{parallel_ops_per_query} ops), capped at {cap}MB for {workload}; raise per role/session for reports",
        },
        "maintenance_work_mem": {
            "value": _mb(mwm),
            "mb": mwm,
            "rationale": "~5 % of RAM up to 2GB: faster VACUUM and CREATE INDEX (autovacuum_max_workers × this)",
        },
        "autovacuum_work_mem": {
            "value": _mb(min(mwm, 1024)),
            "mb": min(mwm, 1024),
            "rationale": "dead-tuple memory per autovacuum worker (≤1GB is useful before PG17)",
        },
    }
    if platform in {"rds", "aurora"}:
        # Parameter groups take raw units: buffers in 8kB pages, the *_mem settings in kB.
        for name, v in out.items():
            paged = name in {"shared_buffers", "effective_cache_size"}
            v["parameter_group_value"] = str(v["mb"] * (128 if paged else 1024))
            v["parameter_group_unit"] = "8kB pages" if paged else "kB"
    return out


# --------------------------------------------------------------------------- read scaling
@dataclass
class ReadScalingPlan:
    read_write_ratio: float
    strategy: list[str]
    readers: int
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d


def read_scaling(
    *,
    reads_per_s: float,
    writes_per_s: float,
    lag_tolerance_s: float,
    primary_cpu_p95: float,
    hot_key_share: float = 0.0,
    target_cpu: float = 60.0,
    engine: str = "aurora-postgresql",
) -> ReadScalingPlan:
    """Replicas scale reads that tolerate staleness; caches absorb hot keys; neither scales writes."""
    ratio = reads_per_s / max(writes_per_s, 1e-9)
    read_share = reads_per_s / max(reads_per_s + writes_per_s, 1e-9)
    findings: list[Finding] = []
    strategy: list[str] = []
    readers = 0
    read_cpu = primary_cpu_p95 * read_share
    if hot_key_share >= 0.2:
        strategy.append("cache")
        findings.append(
            Finding(
                "CACHE_HOT_KEYS",
                "medium",
                f"{hot_key_share:.0%} of reads hit a small hot key set",
                "Cache-aside in Redis (deploy/helm/redis, deploy/terraform/modules/redis) with a TTL and explicit "
                "invalidation on write; protect against stampedes (request coalescing / jittered TTL).",
                "reads",
                {"hot_key_share": hot_key_share},
            )
        )
    if ratio >= 4 and lag_tolerance_s >= 1.0 and primary_cpu_p95 >= target_cpu * 0.66:
        readers = max(1, math.ceil(read_cpu / target_cpu))
        strategy.append("read-replicas")
        lag = (
            "typically < 100 ms (shared storage)"
            if engine.startswith("aurora")
            else "seconds under load (async WAL)"
        )
        findings.append(
            Finding(
                "ADD_READ_REPLICAS",
                "medium",
                f"Read/write ratio {ratio:.1f}:1 with {lag_tolerance_s:g}s staleness tolerated; reads drive "
                f"~{read_cpu:.0f}% primary CPU",
                f"Route read-only, staleness-tolerant queries to {readers} reader(s) (Aurora reader endpoint; "
                f"replica lag {lag}). Keep read-your-writes paths on the writer; use reader auto scaling for bursts.",
                "reads",
                {"readers": readers, "read_cpu_pct": round(read_cpu, 1)},
            )
        )
    elif ratio >= 4 and lag_tolerance_s < 1.0:
        findings.append(
            Finding(
                "REPLICA_LAG_INTOLERANT",
                "low",
                "Reads dominate but cannot tolerate replica lag",
                "Scale the writer vertically, cut work per read (indexes, covering indexes) or use CQRS: a "
                "purpose-built read model updated from the write path (outbox → Kafka → projection).",
                "reads",
                {"lag_tolerance_s": lag_tolerance_s},
            )
        )
    if ratio < 1 and primary_cpu_p95 >= target_cpu:
        findings.append(
            Finding(
                "WRITE_BOUND",
                "high",
                f"Write-heavy ({ratio:.2f}:1) and primary CPU p95 {primary_cpu_p95:.0f}%",
                "Replicas will not help: batch writes, drop unused indexes (write amplification), partition hot "
                "tables, then scale up; beyond one node consider sharding (Citus) by tenant/merchant.",
                "writes",
                {"cpu_p95": primary_cpu_p95},
            )
        )
    if not strategy:
        strategy.append("none-needed")
    return ReadScalingPlan(
        read_write_ratio=round(ratio, 2), strategy=strategy, readers=readers, findings=findings
    )


# --------------------------------------------------------------------------- partitioning
def partitioning_plan(
    tables: list[dict[str, Any]],
    *,
    min_size_gb: float = 100.0,
    min_range_share: float = 0.5,
) -> list[Finding]:
    """Tables ≥ ``min_size_gb`` with a time column that most queries range-filter on → range partitions.

    Each table dict: ``name, size_gb, timestamp_column, range_predicate_share, growth_gb_per_month,
    retention_months`` (optional).
    """
    findings: list[Finding] = []
    for t in tables:
        size = float(t.get("size_gb", 0))
        col = t.get("timestamp_column")
        share = float(t.get("range_predicate_share", 0))
        growth = float(t.get("growth_gb_per_month", 0))
        if size < min_size_gb or not col:
            continue
        if share < min_range_share:
            findings.append(
                Finding(
                    "PARTITIONING_NOT_INDICATED",
                    "info",
                    f"{t['name']} is {size:,.0f} GB but only {share:.0%} of queries filter on {col}",
                    "Partitioning without pruning makes most queries slower (they touch every partition); fix "
                    "indexes first or partition by the column queries do filter on.",
                    t["name"],
                    {"size_gb": size, "range_predicate_share": share},
                )
            )
            continue
        interval = "day" if growth >= 500 else "month"
        retention = t.get("retention_months")
        ddl = (
            f"CREATE TABLE {t['name']}_p (LIKE {t['name']} INCLUDING ALL) PARTITION BY RANGE ({col}); "
            f"-- then partman.create_parent('public.{t['name']}_p', '{col}', '1 {interval}') and migrate in batches"
        )
        findings.append(
            Finding(
                "PARTITION_BY_RANGE",
                "medium" if size < 1000 else "high",
                f"{t['name']}: {size:,.0f} GB, {share:.0%} of queries range-filter on {col}, +{growth:,.0f} GB/month",
                f"Declarative range partitioning by {interval}: {ddl}. Primary key must include {col}; "
                + (
                    f"retention of {retention} months becomes DETACH PARTITION … CONCURRENTLY + DROP instead of DELETE (no bloat)."
                    if retention
                    else "old data is archived by DETACH PARTITION instead of DELETE."
                ),
                t["name"],
                {"size_gb": size, "range_predicate_share": share, "interval": interval},
            )
        )
        if size >= 10_000:
            findings.append(
                Finding(
                    "CONSIDER_SHARDING",
                    "low",
                    f"{t['name']} exceeds 10 TB",
                    "Single-node limits (vacuum duration, backup/restore time) start to dominate: evaluate "
                    "sharding by tenant (Citus) or moving cold partitions to S3 (Parquet) via an archive job.",
                    t["name"],
                    {"size_gb": size},
                )
            )
    return findings


# --------------------------------------------------------------------------- rightsizing
@dataclass
class RightsizingResult:
    current_class: str
    recommended_class: str
    cpu_p95: float
    required_vcpu: float
    required_memory_gb: float
    instance_count: int
    io_share_of_cost: float
    storage_config: str
    current_monthly: float
    recommended_monthly: float
    monthly_savings: float
    illustrative_prices: bool
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d


def _family(cls: str) -> str:
    return cls.split(".")[1] if cls.count(".") >= 2 else cls


def rightsize(
    *,
    current_class: str,
    cpu_pct: list[float],
    freeable_memory_gb: list[float],
    read_iops: list[float],
    write_iops: list[float],
    storage_gb: float,
    instance_count: int = 1,
    current_storage_config: str = "standard",
    headroom: float = 0.3,
    cache_hit_ratio: float | None = None,
    price_table: dict[str, Any] | None = None,
) -> RightsizingResult:
    prices = price_table or load_price_table()
    instances: dict[str, dict[str, Any]] = prices["instances"]
    if current_class not in instances:
        raise KeyError(f"{current_class!r} not in price table; add it before rightsizing")
    cur = instances[current_class]
    hours = float(prices.get("hours_per_month", HOURS_PER_MONTH))
    cpu_p95 = _percentile(cpu_pct, 95)
    required_vcpu = cur["vcpu"] * cpu_p95 / 100 * (1 + headroom)
    used_mem = cur["memory_gb"] - _percentile(freeable_memory_gb, 5)
    required_mem = used_mem * (1 + headroom)
    if cache_hit_ratio is not None and cache_hit_ratio < 0.99:
        required_mem = max(required_mem, cur["memory_gb"])  # working set does not fit: never shrink memory
    findings: list[Finding] = []

    fitting = [
        (name, spec)
        for name, spec in instances.items()
        if spec["vcpu"] >= required_vcpu and spec["memory_gb"] >= required_mem
    ]
    # Cheapest that fits; ties → Graviton, then the current class (no churn).
    fitting.sort(key=lambda kv: (kv[1]["hourly"], not kv[1].get("graviton", False), kv[0] != current_class))
    rec_name, rec = fitting[0] if fitting else (current_class, cur)

    # Aurora I/O-Optimized vs Standard, using mean IOPS across the window.
    io_req_month = (
        (sum(read_iops) / max(len(read_iops), 1) + sum(write_iops) / max(len(write_iops), 1)) * 3600 * hours
    )
    io_cost = io_req_month / 1e6 * float(prices["io"]["standard_per_million"])
    mult = float(prices["io_optimized"]["instance_multiplier"])
    break_even = float(prices["io_optimized"]["break_even_io_share"])

    def bill(spec: dict[str, Any], config: str) -> float:
        compute = spec["hourly"] * hours * instance_count
        if config == "io-optimized":
            return compute * mult + storage_gb * float(prices["storage"]["io_optimized_gb_month"])
        return compute + storage_gb * float(prices["storage"]["standard_gb_month"]) + io_cost

    current_monthly = bill(cur, current_storage_config)
    std_bill = bill(rec, "standard")
    io_share = io_cost / std_bill if std_bill else 0.0
    opt_bill = bill(rec, "io-optimized")
    config = "io-optimized" if io_share >= break_even and opt_bill < std_bill else "standard"
    recommended_monthly = min(std_bill, opt_bill) if config == "io-optimized" else std_bill

    if rec_name != current_class:
        findings.append(
            Finding(
                "RIGHTSIZE_INSTANCE",
                "medium",
                f"{current_class} → {rec_name}: CPU p95 {cpu_p95:.0f}% needs {required_vcpu:.1f} vCPU and "
                f"{required_mem:.0f} GiB with {headroom:.0%} headroom",
                "Modify the reader first, fail over, then the old writer (Aurora: one failover ~30 s; use RDS Proxy "
                "to hold client connections). Re-check cache hit and p99 latency for a week before the next step.",
                current_class,
                {"from": current_class, "to": rec_name, "vcpu": rec["vcpu"], "memory_gb": rec["memory_gb"]},
            )
        )
    if not cur.get("graviton") and rec.get("graviton"):
        findings.append(
            Finding(
                "GRAVITON",
                "info",
                f"{rec_name} is Graviton (arm64): typically ~10-20 % better price-performance than x86 peers",
                "No application change for managed PostgreSQL; validate extensions and benchmark p99 before cut-over.",
                rec_name,
            )
        )
    if config != current_storage_config:
        findings.append(
            Finding(
                "AURORA_IO_OPTIMIZED" if config == "io-optimized" else "AURORA_STANDARD",
                "medium",
                f"I/O is {io_share:.0%} of the Aurora Standard bill (break-even ~{break_even:.0%}); "
                f"{config} costs ${min(std_bill, opt_bill):,.0f}/month vs ${max(std_bill, opt_bill):,.0f}",
                f"Switch the cluster storage type to {'aurora-iopt1' if config == 'io-optimized' else 'aurora'} "
                "(terraform var io_optimized in deploy/terraform/modules/aws/aurora-postgres); changes are limited "
                "to once per 30 days in that direction.",
                "storage",
                {"io_cost_monthly": round(io_cost, 2), "io_share": round(io_share, 4)},
            )
        )
    return RightsizingResult(
        current_class=current_class,
        recommended_class=rec_name,
        cpu_p95=round(cpu_p95, 2),
        required_vcpu=round(required_vcpu, 2),
        required_memory_gb=round(required_mem, 1),
        instance_count=instance_count,
        io_share_of_cost=round(io_share, 4),
        storage_config=config,
        current_monthly=round(current_monthly, 2),
        recommended_monthly=round(recommended_monthly, 2),
        monthly_savings=round(current_monthly - recommended_monthly, 2),
        illustrative_prices=bool(prices.get("illustrative", False)),
        findings=findings,
    )


# --------------------------------------------------------------------------- one-shot report
@dataclass
class CapacityReport:
    pool: PoolSizing
    memory: dict[str, dict[str, Any]]
    read_scaling: ReadScalingPlan
    partitioning: list[Finding]
    rightsizing: RightsizingResult
    findings: list[Finding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool": self.pool.to_dict(),
            "memory": self.memory,
            "read_scaling": self.read_scaling.to_dict(),
            "partitioning": [f.to_dict() for f in self.partitioning],
            "rightsizing": self.rightsizing.to_dict(),
            "findings": [f.to_dict() for f in self.findings],
            "severity_counts": severity_counts(self.findings),
        }


def assess_capacity(profile: dict[str, Any], *, price_table: dict[str, Any] | None = None) -> CapacityReport:
    """Run every capacity check on one profile document (see :func:`sample_capacity_profile`)."""
    prices = price_table or load_price_table()
    inst = profile["instance"]
    spec = prices["instances"][inst["class"]]
    app = profile["application"]
    samples = profile["samples"]
    pool = pool_sizing(
        cores=spec["vcpu"],
        app_instances=app["instances"],
        pool_size_per_instance=app["pool_size_per_instance"],
        max_connections=inst["max_connections"],
    )
    memory = memory_parameters(
        ram_gb=spec["memory_gb"],
        max_connections=min(inst["max_connections"], pool.server_connections)
        if app.get("pgbouncer", True)
        else inst["max_connections"],
        workload=profile.get("workload", "oltp"),
        platform=inst.get("platform", "aurora"),
    )
    reads = read_scaling(
        reads_per_s=app["reads_per_s"],
        writes_per_s=app["writes_per_s"],
        lag_tolerance_s=app["replica_lag_tolerance_s"],
        primary_cpu_p95=_percentile(samples["cpu_pct"], 95),
        hot_key_share=app.get("hot_key_share", 0.0),
        engine=inst.get("engine", "aurora-postgresql"),
    )
    parts = partitioning_plan(profile.get("tables", []))
    rs = rightsize(
        current_class=inst["class"],
        cpu_pct=samples["cpu_pct"],
        freeable_memory_gb=samples["freeable_memory_gb"],
        read_iops=samples["read_iops"],
        write_iops=samples["write_iops"],
        storage_gb=inst["storage_gb"],
        instance_count=inst.get("instance_count", 1),
        current_storage_config=inst.get("storage_config", "standard"),
        cache_hit_ratio=profile.get("cache_hit_ratio"),
        price_table=prices,
    )
    all_findings = sort_findings([*pool.findings, *reads.findings, *parts, *rs.findings])
    return CapacityReport(pool, memory, reads, parts, rs, all_findings)
