"""Index advisor and vacuum / bloat health from catalog snapshots.

The snapshot is one JSON document assembled from read-only catalog queries (see
``docs/database/README.md`` for the exact SQL)::

    {
      "captured_at": "2026-10-13T08:00:00Z",
      "stats_reset": "2026-07-01T00:00:00Z",           # pg_stat_database.stats_reset
      "database": {"datname": "payments", "datfrozenxid_age": 1150000000,
                   "autovacuum_freeze_max_age": 200000000},
      "tables":  [pg_stat_user_tables row + "size_bytes", "relfrozenxid_age"],
      "indexes": [pg_stat_user_indexes row + "indexdef" (pg_indexes), "size_bytes",
                  "is_unique", "is_primary"],
      "foreign_keys": [{"table", "constraint", "columns": [...], "referenced_table"}]
    }

Rules: unused, duplicate and prefix-redundant indexes; foreign keys without a supporting index; tables
with heavy sequential scanning (``seq_scan × n_live_tup``); write amplification from many indexes with
few HOT updates; dead-tuple bloat, stale autovacuum and transaction-ID wraparound risk, with per-table
autovacuum storage parameters.

MySQL / InnoDB: ``sys.schema_unused_indexes`` and ``sys.schema_redundant_indexes`` cover the first two
rules; InnoDB has no VACUUM — purge lag shows as a growing *history list length*
(``SHOW ENGINE INNODB STATUS``) caused by long transactions, and secondary indexes on InnoDB always
include the primary key (so ``(a)`` + PK ``(id)`` already covers ``(a, id)``).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from golden.database.findings import Finding, index_name, quote_ident, severity_counts, sort_findings

XID_LIMIT = 2**31  # transaction IDs wrap at 2^31; PostgreSQL stops accepting writes ~3M before
MIN_UNUSED_BYTES = 1 << 20
SEQ_SCAN_PRESSURE = 1e10  # seq_scan × n_live_tup
DEAD_RATIO_WARN = 0.2
DEAD_RATIO_HIGH = 0.4
AUTOVACUUM_STALE_DAYS = 7
MANY_INDEXES = 6

_INDEXDEF = re.compile(
    r"CREATE\s+(?P<unique>UNIQUE\s+)?INDEX\s+(?:CONCURRENTLY\s+)?(?:IF NOT EXISTS\s+)?(?P<name>\S+)\s+ON\s+"
    r"(?:ONLY\s+)?(?P<table>\S+)\s+USING\s+(?P<method>\w+)\s+\((?P<cols>.*?)\)"
    r"(?:\s+INCLUDE\s+\((?P<include>.*?)\))?(?:\s+(?:NULLS\s+(?:NOT\s+)?DISTINCT\s*))?"
    r"(?:\s+WITH\s+\(.*?\))?(?:\s+WHERE\s+(?P<where>.*))?$",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class IndexDef:
    name: str
    table: str
    method: str
    columns: tuple[str, ...]
    include: tuple[str, ...] = ()
    predicate: str = ""
    unique: bool = False


def _split_cols(text: str) -> tuple[str, ...]:
    out, depth, cur = [], 0, ""
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return tuple(c.strip('"') for c in out)


def parse_indexdef(indexdef: str) -> IndexDef:
    """Parse ``pg_indexes.indexdef`` (``pg_get_indexdef``) output."""
    m = _INDEXDEF.match(indexdef.strip().rstrip(";"))
    if not m:
        raise ValueError(f"unrecognised index definition: {indexdef!r}")
    table = m.group("table").removeprefix("public.")
    return IndexDef(
        name=m.group("name"),
        table=table,
        method=m.group("method").lower(),
        columns=_split_cols(m.group("cols")),
        include=_split_cols(m.group("include") or ""),
        predicate=(m.group("where") or "").strip(),
        unique=bool(m.group("unique")),
    )


def _bare(col: str) -> str:
    """Column name without ordering / opclass decoration: ``created_at DESC`` → ``created_at``."""
    return col.split()[0].strip('"') if col and "(" not in col else col


@dataclass
class TableHealth:
    table: str
    n_live_tup: int
    n_dead_tup: int
    dead_ratio: float
    last_autovacuum_days: float | None
    index_count: int
    hot_update_ratio: float | None
    write_amplification: float
    seq_scan_pressure: float
    autovacuum_settings: dict[str, float | int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class IndexReport:
    totals: dict[str, Any]
    tables: list[TableHealth]
    findings: list[Finding] = field(default_factory=list)
    statements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totals": self.totals,
            "tables": [t.to_dict() for t in self.tables],
            "findings": [f.to_dict() for f in self.findings],
            "severity_counts": severity_counts(self.findings),
            "statements": self.statements,
        }


def _ts(value: Any) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _human(n: float) -> str:
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} TB"


def autovacuum_settings(n_live_tup: int, *, insert_heavy: bool = False) -> dict[str, float | int]:
    """Per-table autovacuum storage parameters that bound dead tuples to an absolute number.

    The global default ``autovacuum_vacuum_scale_factor = 0.2`` waits for 20 % of a table to be dead —
    200M rows on a 1B-row table. Large tables get a smaller scale factor so vacuum runs little and often.
    """
    if n_live_tup >= 100_000_000:
        scale = 0.01
    elif n_live_tup >= 10_000_000:
        scale = 0.02
    elif n_live_tup >= 1_000_000:
        scale = 0.05
    else:
        return {}
    out: dict[str, float | int] = {
        "autovacuum_vacuum_scale_factor": scale,
        "autovacuum_vacuum_threshold": 1000,
        "autovacuum_analyze_scale_factor": scale / 2,
        "autovacuum_vacuum_cost_limit": 2000,
    }
    if insert_heavy:  # PostgreSQL 13+: vacuum append-only tables for the visibility map / freezing
        out["autovacuum_vacuum_insert_scale_factor"] = scale
    return out


def _alter_table(table: str, settings: dict[str, float | int]) -> str:
    body = ", ".join(f"{k} = {v}" for k, v in settings.items())
    return f"ALTER TABLE {table} SET ({body});"


def analyse_indexes(
    snapshot: dict[str, Any],
    *,
    min_unused_bytes: int = MIN_UNUSED_BYTES,
    seq_scan_pressure: float = SEQ_SCAN_PRESSURE,
    now: datetime | None = None,
) -> IndexReport:
    findings: list[Finding] = []
    stmts: list[str] = []
    now = now or _ts(snapshot.get("captured_at")) or datetime.now(UTC)
    stats_reset = _ts(snapshot.get("stats_reset"))
    stats_days = (now - stats_reset).days if stats_reset else None

    indexes = snapshot.get("indexes", [])
    by_table: dict[str, list[tuple[dict[str, Any], IndexDef]]] = defaultdict(list)
    for row in indexes:
        d = parse_indexdef(row["indexdef"])
        by_table[d.table].append((row, d))

    # --- unused ---------------------------------------------------------------
    unused_bytes = 0
    for row in indexes:
        if row.get("is_primary") or row.get("is_unique") or int(row.get("idx_scan", 0)) > 0:
            continue
        size = int(row.get("size_bytes", 0))
        if size < min_unused_bytes:
            continue
        unused_bytes += size
        stmt = f"DROP INDEX CONCURRENTLY IF EXISTS {row['indexrelname']};"
        stmts.append(stmt)
        caveat = (
            f"stats cover {stats_days} days"
            if stats_days is not None
            else "check pg_stat_database.stats_reset"
        )
        findings.append(
            Finding(
                "UNUSED_INDEX",
                "high" if size >= 1 << 30 else "medium",
                f"{row['indexrelname']} on {row['relname']} has never been scanned and costs {_human(size)}",
                f"Confirm idx_scan = 0 on every replica too ({caveat}; month-end jobs!), save the definition, then "
                f"{stmt} Every index slows every INSERT and non-HOT UPDATE.",
                row["indexrelname"],
                {"size_bytes": size, "idx_scan": 0, "stats_age_days": stats_days},
            )
        )

    # --- duplicate / redundant -----------------------------------------------
    for table, items in by_table.items():
        for i, (row_a, a) in enumerate(items):
            for row_b, b in items[i + 1 :] + items[:i]:
                if a.method != "btree" or b.method != "btree" or a.predicate != b.predicate:
                    continue
                if a.unique or row_a.get("is_primary"):
                    continue  # constraints must stay even if redundant for reads
                same = a.columns == b.columns and a.include == b.include
                if same and (b.unique or row_b.get("is_primary") or a.name > b.name):
                    keep = b.name
                    findings.append(
                        Finding(
                            "DUPLICATE_INDEX",
                            "medium",
                            f"{a.name} duplicates {keep} on {table} ({', '.join(a.columns)})",
                            f"DROP INDEX CONCURRENTLY IF EXISTS {a.name};",
                            a.name,
                            {"duplicate_of": keep, "size_bytes": int(row_a.get("size_bytes", 0))},
                        )
                    )
                    stmts.append(f"DROP INDEX CONCURRENTLY IF EXISTS {a.name};")
                    break
                a_cols = [_bare(c) for c in a.columns]
                b_cols = [_bare(c) for c in b.columns]
                if len(a_cols) < len(b_cols) and b_cols[: len(a_cols)] == a_cols and not a.include:
                    findings.append(
                        Finding(
                            "REDUNDANT_INDEX",
                            "low",
                            f"{a.name} ({', '.join(a.columns)}) is a left prefix of {b.name} ({', '.join(b.columns)})",
                            f"{b.name} serves the same lookups; DROP INDEX CONCURRENTLY IF EXISTS {a.name}; "
                            "(keep it only if the wider index is much larger and the narrow one is very hot).",
                            a.name,
                            {
                                "covered_by": b.name,
                                "size_bytes": int(row_a.get("size_bytes", 0)),
                                "idx_scan": int(row_a.get("idx_scan", 0)),
                            },
                        )
                    )
                    stmts.append(f"DROP INDEX CONCURRENTLY IF EXISTS {a.name};")
                    break

    # --- foreign keys without an index ---------------------------------------
    tables = {t["relname"]: t for t in snapshot.get("tables", [])}
    for fk in snapshot.get("foreign_keys", []):
        cols = list(fk["columns"])
        table = fk["table"]
        covered = any(
            [_bare(c) for c in d.columns[: len(cols)]] == cols and d.method == "btree" and not d.predicate
            for _, d in by_table.get(table, [])
        )
        if covered:
            continue
        t = tables.get(table, {})
        rows = int(t.get("n_live_tup", 0))
        stmt = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name(table, cols)} ON {table} ({', '.join(quote_ident(c) for c in cols)});"
        stmts.append(stmt)
        findings.append(
            Finding(
                "FK_WITHOUT_INDEX",
                "high" if rows >= 1_000_000 else "medium",
                f"Foreign key {fk.get('constraint', '')} {table}({', '.join(cols)}) → {fk['referenced_table']} has no "
                "supporting index",
                f"{stmt} Without it every DELETE/UPDATE of a {fk['referenced_table']} key scans {table} "
                "(and holds locks meanwhile), and joins on the key cannot use an index.",
                f"{table}({', '.join(cols)})",
                {"n_live_tup": rows},
            )
        )

    # --- per-table health -----------------------------------------------------
    health: list[TableHealth] = []
    for name, t in sorted(tables.items()):
        live = int(t.get("n_live_tup", 0))
        dead = int(t.get("n_dead_tup", 0))
        dead_ratio = dead / (live + dead) if live + dead else 0.0
        ins, upd, dele = (int(t.get(k, 0)) for k in ("n_tup_ins", "n_tup_upd", "n_tup_del"))
        hot = int(t.get("n_tup_hot_upd", 0))
        idx_count = len(by_table.get(name, []))
        writes = ins + upd + dele
        # Heap write + one entry per index for inserts and non-HOT updates (deletes touch indexes later, in vacuum).
        index_writes = idx_count * (ins + (upd - hot))
        write_amp = 1 + index_writes / writes if writes else 1.0
        hot_ratio = hot / upd if upd else None
        last_av = _ts(t.get("last_autovacuum")) or _ts(t.get("last_vacuum"))
        av_days = (now - last_av).total_seconds() / 86400 if last_av else None
        pressure = float(t.get("seq_scan", 0)) * live
        settings = autovacuum_settings(live, insert_heavy=writes > 0 and ins / writes > 0.9)
        th = TableHealth(
            table=name,
            n_live_tup=live,
            n_dead_tup=dead,
            dead_ratio=round(dead_ratio, 4),
            last_autovacuum_days=round(av_days, 1) if av_days is not None else None,
            index_count=idx_count,
            hot_update_ratio=round(hot_ratio, 4) if hot_ratio is not None else None,
            write_amplification=round(write_amp, 2),
            seq_scan_pressure=pressure,
            autovacuum_settings=settings,
        )
        health.append(th)

        if pressure >= seq_scan_pressure:
            findings.append(
                Finding(
                    "SEQ_SCAN_HEAVY",
                    "high" if pressure >= seq_scan_pressure * 100 else "medium",
                    f"{name}: {int(t.get('seq_scan', 0)):,} sequential scans × {live:,} rows",
                    "Find the statements with `golden db workload` (top by I/O) and EXPLAIN them; add the index "
                    "the filter needs, or accept it if the table is tiny/warehouse-style.",
                    name,
                    {
                        "seq_scan": int(t.get("seq_scan", 0)),
                        "n_live_tup": live,
                        "idx_scan": int(t.get("idx_scan", 0)),
                    },
                )
            )
        if idx_count >= MANY_INDEXES and upd > 0 and (hot_ratio or 0) < 0.5:
            findings.append(
                Finding(
                    "WRITE_AMPLIFICATION",
                    "medium",
                    f"{name}: {idx_count} indexes and {hot_ratio or 0:.0%} HOT updates → ~{write_amp:.1f}x writes per row change",
                    f"Drop unused/redundant indexes on {name}; leave free space for HOT updates "
                    f"(`ALTER TABLE {name} SET (fillfactor = 85);` affects new pages — pg_repack to rewrite); avoid "
                    "indexing frequently updated columns.",
                    name,
                    {
                        "index_count": idx_count,
                        "hot_update_ratio": hot_ratio,
                        "write_amplification": round(write_amp, 2),
                    },
                )
            )
        if dead_ratio >= DEAD_RATIO_WARN and dead >= 10_000:
            fix = _alter_table(name, settings) if settings else f"VACUUM (VERBOSE, ANALYZE) {name};"
            if settings:
                stmts.append(fix)
            findings.append(
                Finding(
                    "TABLE_BLOAT",
                    "high" if dead_ratio >= DEAD_RATIO_HIGH else "medium",
                    f"{name}: {dead_ratio:.0%} dead tuples ({dead:,}); "
                    f"last autovacuum {'never' if av_days is None else f'{av_days:.0f} days ago'}",
                    f"Check for long-running / idle-in-transaction sessions and abandoned replication slots holding "
                    f"the xmin horizon (they block cleanup), then `VACUUM (VERBOSE, ANALYZE) {name};` and tune: {fix} "
                    "Reclaim disk with pg_repack (online), not VACUUM FULL (ACCESS EXCLUSIVE lock).",
                    name,
                    {"dead_ratio": round(dead_ratio, 4), "n_dead_tup": dead, "last_autovacuum_days": av_days},
                )
            )
        elif av_days is not None and av_days >= AUTOVACUUM_STALE_DAYS and dead >= 100_000:
            findings.append(
                Finding(
                    "AUTOVACUUM_STALE",
                    "low",
                    f"{name}: last autovacuum {av_days:.0f} days ago with {dead:,} dead tuples",
                    _alter_table(name, settings) if settings else f"VACUUM (ANALYZE) {name};",
                    name,
                    {"last_autovacuum_days": round(av_days, 1), "n_dead_tup": dead},
                )
            )
        rel_age = int(t.get("relfrozenxid_age", 0))
        if rel_age >= XID_LIMIT * 0.5:
            findings.append(
                Finding(
                    "TABLE_XID_AGE",
                    "high",
                    f"{name}: relfrozenxid age {rel_age:,} ({rel_age / XID_LIMIT:.0%} of wraparound)",
                    f"`VACUUM (FREEZE, VERBOSE) {name};` in a quiet window; keep autovacuum workers unblocked.",
                    name,
                    {"relfrozenxid_age": rel_age},
                )
            )

    # --- database-level wraparound -------------------------------------------
    db = snapshot.get("database", {})
    age = int(db.get("datfrozenxid_age", 0))
    freeze_max = int(db.get("autovacuum_freeze_max_age", 200_000_000))
    pct = age / XID_LIMIT
    if age >= freeze_max:
        sev = "critical" if pct >= 0.75 else "high" if pct >= 0.5 else "low"
        findings.append(
            Finding(
                "XID_WRAPAROUND_RISK",
                sev,
                f"Database {db.get('datname', '')}: age(datfrozenxid) = {age:,} ({pct:.0%} of the 2^31 limit; "
                f"anti-wraparound autovacuum starts at {freeze_max:,})",
                "Find the oldest tables (`ORDER BY age(relfrozenxid) DESC`), remove what blocks freezing (long "
                "transactions, prepared transactions, stale replication slots) and run VACUUM (FREEZE) on them; "
                "alert at 50 % (database_rules.yml PostgresXIDWraparoundRisk).",
                str(db.get("datname", "")),
                {
                    "datfrozenxid_age": age,
                    "pct_of_limit": round(pct, 4),
                    "autovacuum_freeze_max_age": freeze_max,
                },
            )
        )

    totals = {
        "tables": len(tables),
        "indexes": len(indexes),
        "unused_index_bytes": unused_bytes,
        "unused_index_size": _human(unused_bytes),
        "datfrozenxid_pct_of_limit": round(pct, 4),
        "stats_age_days": stats_days,
    }
    health.sort(key=lambda h: (h.dead_ratio, h.seq_scan_pressure), reverse=True)
    return IndexReport(
        totals=totals,
        tables=health,
        findings=sort_findings(findings),
        statements=list(dict.fromkeys(stmts)),
    )
