"""Workload analysis from a ``pg_stat_statements`` export.

Input is a CSV or JSON export of::

    SELECT queryid, query, calls, total_exec_time, mean_exec_time, rows,
           shared_blks_hit, shared_blks_read, temp_blks_written
      FROM pg_stat_statements WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database());

(times in milliseconds, PostgreSQL 13+ column names; ``total_time``/``mean_time`` from 12 and older are
accepted too). The analysis is deterministic and explainable:

* **top offenders** by total time (where the database spends its time — fix these first), by mean time
  (what users feel) and by I/O (blocks read from outside shared_buffers);
* **cache hit ratio** per query ``hit / (hit + read)`` — OLTP targets ≥ 0.99;
* **temp spill** — ``temp_blks_written > 0`` means a sort/hash exceeded ``work_mem``;
* **N+1 suspects** — very high call counts, sub-millisecond mean, ≤ 2 rows per call, lookup by a single
  ``*_id`` foreign-key column (the child fetch an ORM issues once per parent row);
* **fingerprints** — queries normalised so variants that differ only in literals or ``IN`` list length
  (different ``queryid`` before PostgreSQL 18) collapse into one shape.

MySQL: the equivalent source is ``performance_schema.events_statements_summary_by_digest``. Rows with
``DIGEST_TEXT`` / ``COUNT_STAR`` / ``SUM_TIMER_WAIT`` (picoseconds) are converted automatically; MySQL has
no buffer-hit counters per digest, so cache-hit rules are skipped for those rows and
``SUM_CREATED_TMP_DISK_TABLES`` stands in for temp spill.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from golden.database.findings import Finding, severity_counts, sort_findings

# Defaults are deliberately conservative; every one is a keyword argument of analyse_workload.
CACHE_HIT_TARGET = 0.99
MIN_BLOCKS_FOR_CACHE_RULE = 10_000
N_PLUS_ONE_MIN_CALLS = 100_000
N_PLUS_ONE_MAX_MEAN_MS = 0.5
N_PLUS_ONE_MAX_ROWS_PER_CALL = 2.0
DOMINANT_SHARE = 0.25
UNBOUNDED_ROWS_PER_CALL = 10_000
PS_PER_MS = 1_000_000_000  # MySQL timer columns are picoseconds


@dataclass
class QueryStat:
    queryid: str
    query: str
    calls: int
    total_exec_time: float  # ms
    mean_exec_time: float  # ms
    rows: int = 0
    shared_blks_hit: int = 0
    shared_blks_read: int = 0
    temp_blks_written: int = 0
    has_buffer_stats: bool = True

    @property
    def cache_hit_ratio(self) -> float | None:
        total = self.shared_blks_hit + self.shared_blks_read
        if not self.has_buffer_stats or total == 0:
            return None
        return self.shared_blks_hit / total

    @property
    def rows_per_call(self) -> float:
        return self.rows / self.calls if self.calls else 0.0

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.query)

    def summary(self, total_time: float) -> dict[str, Any]:
        hit = self.cache_hit_ratio
        return {
            "queryid": self.queryid,
            "fingerprint": _short(self.fingerprint),
            "calls": self.calls,
            "total_exec_time_ms": round(self.total_exec_time, 1),
            "mean_exec_time_ms": round(self.mean_exec_time, 3),
            "share_of_total_time": round(self.total_exec_time / total_time, 4) if total_time else 0.0,
            "rows_per_call": round(self.rows_per_call, 2),
            "shared_blks_read": self.shared_blks_read,
            "cache_hit_ratio": round(hit, 4) if hit is not None else None,
            "temp_blks_written": self.temp_blks_written,
        }


@dataclass
class WorkloadReport:
    totals: dict[str, Any]
    top_by_total_time: list[dict[str, Any]]
    top_by_mean_time: list[dict[str, Any]]
    top_by_io: list[dict[str, Any]]
    fingerprints: list[dict[str, Any]]
    findings: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totals": self.totals,
            "top_by_total_time": self.top_by_total_time,
            "top_by_mean_time": self.top_by_mean_time,
            "top_by_io": self.top_by_io,
            "fingerprints": self.fingerprints,
            "findings": [f.to_dict() for f in self.findings],
            "severity_counts": severity_counts(self.findings),
        }


# --------------------------------------------------------------------------- fingerprints
_COMMENT = re.compile(r"/\*.*?\*/|--[^\n]*", re.DOTALL)
_STRING = re.compile(r"'(?:[^']|'')*'")
_NUMBER = re.compile(r"(?<![\w$])-?\d+(?:\.\d+)?(?:e[+-]?\d+)?\b", re.IGNORECASE)
_PARAM = re.compile(r"\$\d+|\?")
_IN_LIST = re.compile(r"\bin\s*\(\s*\?(?:\s*,\s*\?)*\s*\)", re.IGNORECASE)
_VALUES_LIST = re.compile(
    r"values\s*(\(\s*\?(?:\s*,\s*\?)*\s*\))(?:\s*,\s*\(\s*\?(?:\s*,\s*\?)*\s*\))+", re.IGNORECASE
)
_WS = re.compile(r"\s+")


def fingerprint(query: str) -> str:
    """Normalise a statement to its shape: literals and parameters → ``?``, IN/VALUES lists collapsed.

    ``SELECT * FROM t WHERE id IN ($1, $2, $3)`` and ``... IN (7, 8)`` share the fingerprint
    ``select * from t where id in (...)``.
    """
    q = _COMMENT.sub(" ", query)
    q = _STRING.sub("?", q)
    q = _PARAM.sub("?", q)
    q = _NUMBER.sub("?", q)
    q = _WS.sub(" ", q).strip().lower().rstrip(";").strip()
    q = _IN_LIST.sub("in (...)", q)
    q = _VALUES_LIST.sub(r"values \1, ...", q)
    return q


def _short(text: str, limit: int = 160) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


_FK_LOOKUP = re.compile(r"^select\b.*\bwhere\s+(?:\w+\.)?\w+_id\s*=\s*\?(\s+(limit|order|for)\b.*)?$")


def _is_fk_lookup(fp: str) -> bool:
    """Single-predicate lookup on a ``*_id`` (foreign-key convention) column: the per-parent child fetch
    an ORM issues in a loop. Primary-key lookups (``id = ?``) are normal OLTP and are not flagged."""
    return " join " not in fp and " and " not in fp and bool(_FK_LOOKUP.match(fp))


# --------------------------------------------------------------------------- loading
def _num(rec: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        v = rec.get(k)
        if v not in (None, ""):
            return float(v)
    return default


def parse_statement(rec: Mapping[str, Any]) -> QueryStat:
    """One export row → :class:`QueryStat` (pg_stat_statements or MySQL digest summary)."""
    if "DIGEST_TEXT" in rec or "digest_text" in rec:
        r = {k.upper(): v for k, v in rec.items()}
        calls = int(_num(r, "COUNT_STAR"))
        total = _num(r, "SUM_TIMER_WAIT") / PS_PER_MS
        return QueryStat(
            queryid=str(r.get("DIGEST", "")),
            query=str(r.get("DIGEST_TEXT", "")),
            calls=calls,
            total_exec_time=total,
            mean_exec_time=_num(r, "AVG_TIMER_WAIT") / PS_PER_MS
            if "AVG_TIMER_WAIT" in r
            else total / max(calls, 1),
            rows=int(_num(r, "SUM_ROWS_SENT")),
            temp_blks_written=int(_num(r, "SUM_CREATED_TMP_DISK_TABLES")),
            has_buffer_stats=False,
        )
    calls = int(_num(rec, "calls"))
    total = _num(rec, "total_exec_time", "total_time")
    return QueryStat(
        queryid=str(rec.get("queryid", "")),
        query=str(rec.get("query", "")),
        calls=calls,
        total_exec_time=total,
        mean_exec_time=_num(rec, "mean_exec_time", "mean_time", default=total / max(calls, 1)),
        rows=int(_num(rec, "rows")),
        shared_blks_hit=int(_num(rec, "shared_blks_hit")),
        shared_blks_read=int(_num(rec, "shared_blks_read")),
        temp_blks_written=int(_num(rec, "temp_blks_written")),
    )


def parse_statements(records: Iterable[Mapping[str, Any]]) -> list[QueryStat]:
    return [parse_statement(r) for r in records]


def load_statements(path: str | Path) -> list[QueryStat]:
    """Load a CSV (header row) or JSON (list of objects, or ``{"statements": [...]}``) export."""
    p = Path(path)
    text = p.read_text("utf-8")
    if p.suffix.lower() == ".json" or text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
        rows = data.get("statements", []) if isinstance(data, dict) else data
        return parse_statements(rows)
    return parse_statements(csv.DictReader(io.StringIO(text)))


# --------------------------------------------------------------------------- analysis
def analyse_workload(
    stats: Iterable[QueryStat],
    *,
    top_n: int = 10,
    cache_hit_target: float = CACHE_HIT_TARGET,
    min_blocks_for_cache_rule: int = MIN_BLOCKS_FOR_CACHE_RULE,
    n_plus_one_min_calls: int = N_PLUS_ONE_MIN_CALLS,
    n_plus_one_max_mean_ms: float = N_PLUS_ONE_MAX_MEAN_MS,
    dominant_share: float = DOMINANT_SHARE,
) -> WorkloadReport:
    rows = [s for s in stats if s.calls > 0]
    total_time = sum(s.total_exec_time for s in rows)
    total_calls = sum(s.calls for s in rows)
    hit = sum(s.shared_blks_hit for s in rows if s.has_buffer_stats)
    read = sum(s.shared_blks_read for s in rows if s.has_buffer_stats)
    findings: list[Finding] = []

    by_total = sorted(rows, key=lambda s: s.total_exec_time, reverse=True)
    by_mean = sorted(rows, key=lambda s: s.mean_exec_time, reverse=True)
    by_io = sorted(rows, key=lambda s: s.shared_blks_read + s.temp_blks_written, reverse=True)

    # Group by fingerprint: the unit an engineer actually fixes.
    groups: dict[str, list[QueryStat]] = defaultdict(list)
    for s in rows:
        groups[s.fingerprint].append(s)
    fp_rows: list[dict[str, Any]] = []
    for fp, members in groups.items():
        t = sum(m.total_exec_time for m in members)
        c = sum(m.calls for m in members)
        fp_rows.append(
            {
                "fingerprint": _short(fp),
                "queryids": sorted(m.queryid for m in members),
                "variants": len(members),
                "calls": c,
                "total_exec_time_ms": round(t, 1),
                "share_of_total_time": round(t / total_time, 4) if total_time else 0.0,
            }
        )
    fp_rows.sort(key=lambda r: r["total_exec_time_ms"], reverse=True)

    for s in rows:
        share = s.total_exec_time / total_time if total_time else 0.0
        ev = {"calls": s.calls, "mean_exec_time_ms": round(s.mean_exec_time, 3), "share": round(share, 4)}
        if share >= dominant_share:
            findings.append(
                Finding(
                    "DOMINANT_QUERY",
                    "high",
                    f"One statement consumes {share:.0%} of total execution time",
                    "Run EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) on it with production-like parameters and "
                    "feed the plan to `golden db explain`; it is the highest-leverage fix.",
                    s.queryid,
                    ev,
                )
            )
        ratio = s.cache_hit_ratio
        if ratio is not None and ratio < cache_hit_target and s.shared_blks_read >= min_blocks_for_cache_rule:
            findings.append(
                Finding(
                    "LOW_CACHE_HIT",
                    "high" if ratio < 0.9 else "medium",
                    f"Cache hit ratio {ratio:.1%} with {s.shared_blks_read:,} blocks read from disk/OS cache",
                    "Reduce pages touched (selective or covering index, narrower SELECT list) before adding RAM; "
                    "if the working set is legitimately large, size shared_buffers / instance memory for it.",
                    s.queryid,
                    {**ev, "cache_hit_ratio": round(ratio, 4), "shared_blks_read": s.shared_blks_read},
                )
            )
        if s.temp_blks_written > 0:
            mb = s.temp_blks_written * 8 / 1024 / max(s.calls, 1)
            findings.append(
                Finding(
                    "TEMP_SPILL",
                    "medium" if mb < 64 else "high",
                    f"Sort/hash spills to disk: {s.temp_blks_written:,} temp blocks (~{mb:.1f} MB per call)",
                    "Add an index that delivers rows pre-sorted, aggregate less, or raise work_mem for this role/"
                    "session only (`SET LOCAL work_mem = '…'`) — never globally without connection math.",
                    s.queryid,
                    {**ev, "temp_blks_written": s.temp_blks_written, "temp_mb_per_call": round(mb, 2)},
                )
            )
        if (
            s.calls >= n_plus_one_min_calls
            and s.mean_exec_time <= n_plus_one_max_mean_ms
            and s.rows_per_call <= N_PLUS_ONE_MAX_ROWS_PER_CALL
            and _is_fk_lookup(s.fingerprint)
        ):
            findings.append(
                Finding(
                    "N_PLUS_ONE_SUSPECT",
                    "medium",
                    f"{s.calls:,} calls of a per-parent foreign-key lookup at {s.mean_exec_time:.3f} ms — round trips, not "
                    "the database, dominate latency",
                    "Batch the lookups in the application: `WHERE key = ANY($1::bigint[])` or a JOIN in the "
                    "parent query; with an ORM use eager loading (select_related / prefetch / includes).",
                    s.queryid,
                    {**ev, "rows_per_call": round(s.rows_per_call, 2)},
                )
            )
        if s.rows_per_call >= UNBOUNDED_ROWS_PER_CALL and s.query.lstrip().lower().startswith("select"):
            findings.append(
                Finding(
                    "UNBOUNDED_RESULT",
                    "medium",
                    f"Returns {s.rows_per_call:,.0f} rows per call",
                    "Paginate with keyset pagination (`WHERE (created_at, id) < ($1, $2) ORDER BY … LIMIT n`) or "
                    "move the aggregation into SQL.",
                    s.queryid,
                    {**ev, "rows_per_call": round(s.rows_per_call, 1)},
                )
            )

    for fp_row in fp_rows:
        if fp_row["variants"] > 1:
            findings.append(
                Finding(
                    "QUERY_SHAPE_VARIANTS",
                    "low",
                    f"{fp_row['variants']} queryids share one shape (literal or IN-list length variants)",
                    "Bind arrays instead of expanding IN lists (`= ANY($1)`), use bind parameters, so one plan and "
                    "one pg_stat_statements entry serve the shape (PostgreSQL 18 also squashes IN lists).",
                    ",".join(fp_row["queryids"]),
                    {"fingerprint": fp_row["fingerprint"], "calls": fp_row["calls"]},
                )
            )

    overall_hit = hit / (hit + read) if hit + read else None
    totals = {
        "statements": len(rows),
        "fingerprints": len(groups),
        "calls": total_calls,
        "total_exec_time_ms": round(total_time, 1),
        "mean_exec_time_ms": round(total_time / total_calls, 4) if total_calls else 0.0,
        "cache_hit_ratio": round(overall_hit, 4) if overall_hit is not None else None,
        "statements_spilling_to_temp": sum(1 for s in rows if s.temp_blks_written > 0),
        "top_n_share_of_time": round(sum(s.total_exec_time for s in by_total[:top_n]) / total_time, 4)
        if total_time
        else 0.0,
    }
    return WorkloadReport(
        totals=totals,
        top_by_total_time=[s.summary(total_time) for s in by_total[:top_n]],
        top_by_mean_time=[s.summary(total_time) for s in by_mean[:top_n]],
        top_by_io=[
            s.summary(total_time) for s in by_io[:top_n] if s.shared_blks_read + s.temp_blks_written > 0
        ],
        fingerprints=fp_rows[:top_n],
        findings=sort_findings(findings),
    )
