"""Rule-based analysis of ``EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`` plans.

Capture a plan with production-like parameters (on a replica or inside a rolled-back transaction for
writes)::

    EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT ...;

Rules (each finding carries the node path, evidence numbers and a concrete remediation):

=====================  ==========================================================================
SEQ_SCAN_SELECTIVE     Seq Scan reads ≥ ``large_rows`` rows but keeps ≤ 5 % → B-tree index on the
                       filter columns (equality columns first, then range), expression index for
                       ``lower(col)``-style filters, ``CREATE INDEX CONCURRENTLY``.
ROW_MISESTIMATE        actual / estimated rows ≥ 10x (either direction) → stale or insufficient
                       statistics: ``ANALYZE``, per-column statistics target, extended statistics
                       for correlated columns.
NESTED_LOOP_LARGE      Nested Loop whose inner side runs ≥ ``loop_threshold`` times; critical when the
                       inner side is a Seq Scan (index the join key).
MISSING_JOIN_INDEX     Hash/Merge Join that reads a large relation in full to produce few rows → index
                       the join key so the planner can use an index nested loop.
INDEX_FILTER_INEFFICIENT  Index Scan whose Filter discards ≥ 90 % of the rows the index returned →
                       widen the index with the filter columns.
SORT_SPILL / HASH_SPILL  Sort ``Sort Space Type: Disk`` or Hash ``Hash Batches > 1`` → work_mem sizing.
LOSSY_BITMAP           Bitmap Heap Scan with lossy blocks → bitmap exceeded work_mem; rows rechecked.
=====================  ==========================================================================

MySQL: use ``EXPLAIN ANALYZE`` (8.0.18+) or ``EXPLAIN FORMAT=JSON``; the same ideas map to
``type: ALL`` (full scan), ``rows`` vs actual, ``Using filesort`` / ``Using temporary`` (tmp_table_size)
and ``Block Nested Loop`` / hash join on unindexed keys. This module parses PostgreSQL JSON only.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from golden.database.findings import Finding, index_name, quote_ident, severity_counts, sort_findings

LARGE_ROWS = 100_000
SELECTIVE_FRACTION = 0.05
MISESTIMATE_RATIO = 10.0
MISESTIMATE_MIN_ROWS = 1_000
LOOP_THRESHOLD = 1_000
BLOCK_KB = 8

_EQ_OPS = {"=", "IS", "= ANY"}
_RANGE_OPS = {"<", ">", "<=", ">="}
_CLAUSE = re.compile(r"^(?P<lhs>.+?)\s*(?P<op>= ANY|<=|>=|<>|!=|=|<|>|~~\*|~~|IS NOT|IS)\s*(?P<rhs>.*)$")
_CAST = re.compile(r"::[a-z_ ]+(?:\[\])?", re.IGNORECASE)
_FUNC = re.compile(r"^(?P<func>lower|upper)\((?P<arg>.+)\)$", re.IGNORECASE)
_IDENT = re.compile(r"^(?:(?P<alias>[a-z_][a-z0-9_]*)\.)?(?P<col>[a-z_][a-z0-9_]*)$", re.IGNORECASE)


@dataclass
class PlanNode:
    node_type: str
    path: str
    raw: dict[str, Any]
    children: list[PlanNode] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    @property
    def relation(self) -> str:
        rel = self.raw.get("Relation Name", "")
        schema = self.raw.get("Schema")
        return f"{schema}.{rel}" if schema and rel and schema != "public" else rel

    @property
    def alias(self) -> str:
        return str(self.raw.get("Alias", self.raw.get("Relation Name", "")))

    @property
    def loops(self) -> int:
        return int(self.raw.get("Actual Loops", 1) or 1)

    @property
    def actual_rows(self) -> float:
        """Rows per loop (PostgreSQL reports Actual Rows averaged per loop)."""
        return float(self.raw.get("Actual Rows", 0))

    @property
    def plan_rows(self) -> float:
        return float(self.raw.get("Plan Rows", 0))

    @property
    def total_rows(self) -> float:
        return self.actual_rows * self.loops

    @property
    def inclusive_ms(self) -> float:
        return float(self.raw.get("Actual Total Time", 0.0)) * self.loops

    @property
    def exclusive_ms(self) -> float:
        return max(0.0, self.inclusive_ms - sum(c.inclusive_ms for c in self.children))


@dataclass
class ExplainReport:
    execution_time_ms: float
    planning_time_ms: float
    node_count: int
    hottest_nodes: list[dict[str, Any]]
    findings: list[Finding] = field(default_factory=list)
    statements: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_time_ms": self.execution_time_ms,
            "planning_time_ms": self.planning_time_ms,
            "node_count": self.node_count,
            "hottest_nodes": self.hottest_nodes,
            "findings": [f.to_dict() for f in self.findings],
            "severity_counts": severity_counts(self.findings),
            "statements": self.statements,
        }


# --------------------------------------------------------------------------- parsing
def _root(plan: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Accept the raw EXPLAIN JSON (a one-element list), the top object, or a bare plan node."""
    if isinstance(plan, str):
        plan = json.loads(plan)
    if isinstance(plan, list):
        if not plan:
            raise ValueError("empty EXPLAIN output")
        plan = plan[0]
    if not isinstance(plan, dict):
        raise ValueError("EXPLAIN JSON must be an object or a list of one object")
    if "Plan" in plan:
        return plan, plan["Plan"]
    if "Node Type" in plan:
        return {}, plan
    raise ValueError("not an EXPLAIN (FORMAT JSON) document: no 'Plan' or 'Node Type' key")


def parse_plan(plan: Any) -> PlanNode:
    _, root = _root(plan)

    def build(raw: dict[str, Any], path: str) -> PlanNode:
        node = PlanNode(str(raw.get("Node Type", "?")), path, raw)
        for i, child in enumerate(raw.get("Plans", []) or []):
            node.children.append(build(child, f"{path}/{i}:{child.get('Node Type', '?')}"))
        return node

    return build(root, f"0:{root.get('Node Type', '?')}")


def walk(node: PlanNode) -> Iterator[PlanNode]:
    yield node
    for c in node.children:
        yield from walk(c)


_BLOCKING = {"Sort", "Hash", "Aggregate", "HashAggregate", "Materialize", "SetOp", "WindowAgg"}


def _with_limit_context(node: PlanNode, limited: bool = False) -> Iterator[tuple[PlanNode, bool]]:
    """Yield (node, is_under_a_streaming_LIMIT). Blocking nodes consume their whole input, ending truncation."""
    yield node, limited
    child_limited = True if node.node_type == "Limit" else (False if node.node_type in _BLOCKING else limited)
    for c in node.children:
        yield from _with_limit_context(c, child_limited)


def load_plan(path: str | Path) -> Any:
    return json.loads(Path(path).read_text("utf-8"))


def _strip_parens(text: str) -> str:
    text = text.strip()
    while text.startswith("(") and text.endswith(")"):
        depth = 0
        for i, ch in enumerate(text):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(text) - 1:
                return text  # the outer parens do not wrap the whole expression
        text = text[1:-1].strip()
    return text


def filter_columns(expr: str, alias: str = "") -> tuple[list[str], list[str], list[str]]:
    """Split a Filter / Cond expression into (equality columns, range columns, expression columns).

    Only AND-ed predicates of the form ``column <op> value`` are B-tree candidates; expression columns are
    function-wrapped (``lower(email)``) and need an expression index. Columns qualified with another alias
    (the other side of a join) are skipped.
    """
    eq: list[str] = []
    rng: list[str] = []
    exprs: list[str] = []
    for clause in re.split(r"\s+AND\s+", _strip_parens(expr), flags=re.IGNORECASE):
        m = _CLAUSE.match(_strip_parens(clause))
        if not m:
            continue
        lhs = _strip_parens(_CAST.sub("", m.group("lhs")))
        op = m.group("op").upper()
        func = ""
        fm = _FUNC.match(lhs)
        if fm:
            func, lhs = fm.group("func").lower(), _strip_parens(_CAST.sub("", fm.group("arg")))
        im = _IDENT.match(lhs)
        if not im:
            continue
        if alias and im.group("alias") and im.group("alias") != alias:
            continue
        col = im.group("col")
        if func:
            item = f"{func}({col})"
            if item not in exprs:
                exprs.append(item)
        elif op in _EQ_OPS:
            if col not in eq:
                eq.append(col)
        elif op in _RANGE_OPS and col not in rng:
            rng.append(col)
    rng = [c for c in rng if c not in eq]
    return eq, rng, exprs


def _create_index(table: str, cols: list[str], *, where: str = "") -> str:
    name = index_name(table, cols)
    rendered = ", ".join(c if "(" in c else quote_ident(c) for c in cols)
    stmt = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} ({rendered})"
    return stmt + (f" WHERE {where}" if where else "") + ";"


def _index_filter(n: PlanNode, out: list[Finding], stmts: list[str]) -> None:
    if n.node_type not in {"Index Scan", "Index Only Scan"} or not n.get("Filter"):
        return
    removed = float(n.get("Rows Removed by Filter", 0)) * n.loops
    if removed < 10_000 or n.total_rows > removed * 0.1:
        return
    ieq, irng, _ = filter_columns(str(n.get("Index Cond", "")), n.alias)
    feq, frng, fexpr = filter_columns(str(n.get("Filter", "")), n.alias)
    cols = list(dict.fromkeys(ieq + feq + fexpr)) + list(dict.fromkeys(irng + frng))[:1]
    if not feq and not fexpr:
        return
    stmt = _create_index(n.relation, cols)
    stmts.append(stmt)
    out.append(
        Finding(
            "INDEX_FILTER_INEFFICIENT",
            "medium",
            f"{n.node_type} using {n.get('Index Name', '?')} discards {int(removed):,} rows by Filter to return "
            f"{int(n.total_rows):,}",
            f"{stmt} Move the filter columns into the index (equality first); append the ORDER BY column "
            "(e.g. created_at DESC) so LIMIT queries stop early. Then drop the narrower index if unused.",
            n.path,
            {
                "rows_removed_by_filter": int(removed),
                "rows_returned": int(n.total_rows),
                "filter": n.get("Filter"),
            },
        )
    )


def _work_mem_mb(kb: float) -> int:
    """Round in-memory need up to a power of two MB. An on-disk sort needs roughly 2-3x its disk size."""
    need_mb = max(4.0, kb * 2.5 / 1024)
    return int(2 ** math.ceil(math.log2(need_mb)))


# --------------------------------------------------------------------------- rules
def _seq_scan(n: PlanNode, large_rows: int, out: list[Finding], stmts: list[str]) -> None:
    removed = float(n.get("Rows Removed by Filter", 0)) * n.loops
    scanned = n.total_rows + removed
    filt = str(n.get("Filter", ""))
    if not filt or scanned < large_rows:
        return
    kept = n.total_rows / scanned if scanned else 1.0
    if kept > SELECTIVE_FRACTION:
        return
    eq, rng, exprs = filter_columns(filt, n.alias)
    cols = exprs + eq + rng[:1]  # equality first, at most one trailing range column
    table = n.relation
    ev = {
        "rows_scanned": int(scanned),
        "rows_returned": int(n.total_rows),
        "selectivity": round(kept, 6),
        "filter": filt,
        "node_ms": round(n.exclusive_ms, 2),
    }
    if not cols:
        remediation = f"Filter is not B-tree indexable as written ({filt}); rewrite it sargable or consider pg_trgm GIN."
    else:
        stmt = _create_index(table, cols)
        stmts.append(stmt)
        why = []
        if exprs:
            why.append("expression index because the filter wraps the column in a function")
        if eq and rng:
            why.append("equality columns before the range column so the range scan stays contiguous")
        remediation = stmt + (f" ({'; '.join(why)})" if why else "") + f" Then ANALYZE {table};"
    out.append(
        Finding(
            "SEQ_SCAN_SELECTIVE",
            "high" if scanned >= 1_000_000 else "medium",
            f"Seq Scan on {table} reads {int(scanned):,} rows to return {int(n.total_rows):,} ({kept:.3%})",
            remediation,
            n.path,
            ev,
        )
    )


def _misestimate_ratio(n: PlanNode) -> float:
    if "Actual Rows" not in n.raw or "Plan Rows" not in n.raw:
        return 1.0
    est, act = n.plan_rows, n.actual_rows
    if max(est, act) * n.loops < MISESTIMATE_MIN_ROWS:
        return 1.0
    return max(est, act) / max(min(est, act), 1.0)


def _misestimate(n: PlanNode, limited: bool, out: list[Finding], stmts: list[str]) -> None:
    ratio = _misestimate_ratio(n)
    if ratio < MISESTIMATE_RATIO:
        return
    est, act = n.plan_rows, n.actual_rows
    if limited and act < est:
        return  # a LIMIT above stopped this node early: fewer actual rows is expected, not a misestimate
    if any(_misestimate_ratio(c) >= MISESTIMATE_RATIO for c in n.children):
        return  # inherited from a child; report only the lowest node where the error originates
    direction = "under" if act > est else "over"
    table = n.relation
    cond = str(n.get("Filter") or n.get("Index Cond") or n.get("Recheck Cond") or "")
    eq, rng, _ = filter_columns(cond, n.alias) if cond else ([], [], [])
    cols = eq + rng
    if table and len(cols) >= 2:
        stx = index_name(table, cols, prefix="stx")
        stmt = f"CREATE STATISTICS IF NOT EXISTS {stx} (dependencies, ndistinct, mcv) ON {', '.join(cols)} FROM {table}; ANALYZE {table};"
        stmts.append(stmt)
        fix = f"Columns {cols} are likely correlated: {stmt}"
    elif table and cols:
        stmt = f"ALTER TABLE {table} ALTER COLUMN {cols[0]} SET STATISTICS 1000; ANALYZE {table};"
        fix = f"Refresh and deepen statistics: ANALYZE {table}; if it persists, {stmt}"
    elif table:
        fix = f"ANALYZE {table}; check pg_stat_user_tables.last_autoanalyze and lower autovacuum_analyze_scale_factor."
    else:
        fix = "Misestimate propagates from a child or join: fix the lowest misestimated scan first (ANALYZE, extended statistics)."
    out.append(
        Finding(
            "ROW_MISESTIMATE",
            "high" if ratio >= 100 and direction == "under" else "medium",
            f"{n.node_type}{' on ' + table if table else ''}: planner {direction}-estimated rows by {ratio:,.0f}x "
            f"(estimated {int(est):,}, actual {int(act):,} per loop)",
            fix,
            n.path,
            {"plan_rows": est, "actual_rows": act, "loops": n.loops, "ratio": round(ratio, 1)},
        )
    )


def _join_key_for(cond: str, alias: str) -> str:
    for side in re.split(r"\s*=\s*", cond.strip("() ")):
        side = side.strip("() ").split("::")[0]
        if "." in side:
            a, col = side.split(".", 1)
            if a == alias:
                return col.strip("() ")
    return ""


def _inner_scan(n: PlanNode) -> PlanNode | None:
    """Descend through Materialize/Hash/Memoize wrappers to the scan feeding a join side."""
    cur: PlanNode | None = n
    while cur is not None and cur.node_type in {"Materialize", "Hash", "Memoize", "Sort"} and cur.children:
        cur = cur.children[0]
    return cur


def _nested_loop(n: PlanNode, loop_threshold: int, out: list[Finding], stmts: list[str]) -> None:
    if n.node_type != "Nested Loop" or len(n.children) < 2:
        return
    inner = _inner_scan(n.children[1])
    if inner is None:
        return
    loops = n.children[1].loops  # rescans of the inner side (a Materialize child itself runs once)
    if loops < loop_threshold:
        return
    outer_alias = n.children[0].alias
    cond = str(n.get("Join Filter") or inner.get("Filter") or inner.get("Index Cond") or "")
    key = _join_key_for(cond, inner.alias) if cond else ""
    ev = {"inner_loops": loops, "inner_node": inner.node_type, "inner_rows_per_loop": inner.actual_rows}
    if inner.node_type == "Seq Scan":
        table = inner.relation
        if key:
            stmt = _create_index(table, [key])
            stmts.append(stmt)
            fix = f"{stmt} so each loop becomes an index lookup (or the planner switches to a hash join)."
        else:
            fix = f"Index the join column of {table} referenced by the join condition."
        out.append(
            Finding(
                "NESTED_LOOP_LARGE",
                "critical",
                f"Nested Loop re-scans {table} sequentially {loops:,} times (outer {outer_alias or 'side'})",
                fix,
                n.path,
                {**ev, "join_condition": cond},
            )
        )
    elif inner.actual_rows * loops >= LARGE_ROWS:
        out.append(
            Finding(
                "NESTED_LOOP_LARGE",
                "medium",
                f"Nested Loop drives {loops:,} inner {inner.node_type}s returning {int(inner.actual_rows * loops):,} rows",
                "Usually caused by an outer-side under-estimate: fix ROW_MISESTIMATE findings first; for "
                "reporting queries a hash join (more work_mem) is cheaper than this many index probes.",
                n.path,
                ev,
            )
        )


def _hash_join_selective(n: PlanNode, large_rows: int, out: list[Finding], stmts: list[str]) -> None:
    if n.node_type not in {"Hash Join", "Merge Join"} or len(n.children) < 2:
        return
    cond = str(n.get("Hash Cond") or n.get("Merge Cond") or "")
    for child in n.children:
        scan = _inner_scan(child)
        if scan is None or scan.node_type != "Seq Scan" or scan.get("Filter"):
            continue
        if scan.total_rows < large_rows or n.total_rows > scan.total_rows * 0.01:
            continue
        key = _join_key_for(cond, scan.alias)
        if not key:
            continue
        stmt = _create_index(scan.relation, [key])
        stmts.append(stmt)
        out.append(
            Finding(
                "MISSING_JOIN_INDEX",
                "medium",
                f"{n.node_type} reads all {int(scan.total_rows):,} rows of {scan.relation} to produce "
                f"{int(n.total_rows):,} rows",
                f"{stmt} — lets the planner probe {scan.relation} by {key} instead of hashing the whole table.",
                n.path,
                {
                    "scanned_rows": int(scan.total_rows),
                    "join_rows": int(n.total_rows),
                    "join_condition": cond,
                },
            )
        )


def _spills(n: PlanNode, out: list[Finding]) -> None:
    if n.node_type in {"Sort", "Incremental Sort"} and n.get("Sort Space Type") == "Disk":
        kb = float(n.get("Sort Space Used", 0))
        mb = _work_mem_mb(kb)
        out.append(
            Finding(
                "SORT_SPILL",
                "high" if kb >= 512 * 1024 else "medium",
                f"Sort on {n.get('Sort Key', [])} spilled {kb / 1024:,.1f} MB to disk ({n.get('Sort Method', '')})",
                f"Prefer an index that returns rows in sort order; otherwise `SET LOCAL work_mem = '{mb}MB'` for "
                "this query/role (work_mem is per sort/hash node per connection — do the max_connections math).",
                n.path,
                {"sort_space_kb": kb, "suggested_work_mem_mb": mb},
            )
        )
    batches = int(n.get("Hash Batches", 1) or 1)
    if n.node_type == "Hash" and batches > 1:
        peak = float(n.get("Peak Memory Usage", 0))
        mb = _work_mem_mb(peak * batches)
        out.append(
            Finding(
                "HASH_SPILL",
                "medium",
                f"Hash split into {batches} batches (original {n.get('Original Hash Batches', batches)}) — "
                "build side did not fit in memory",
                f"`SET LOCAL work_mem = '{mb}MB'` (or raise hash_mem_multiplier, default 2.0 in PG15+) for this "
                "workload; also check the build side is the smaller relation (row estimates).",
                n.path,
                {"hash_batches": batches, "peak_memory_kb": peak, "suggested_work_mem_mb": mb},
            )
        )
    if n.node_type in {"HashAggregate", "Aggregate"} and int(n.get("HashAgg Batches", 0) or 0) > 1:
        out.append(
            Finding(
                "HASH_SPILL",
                "medium",
                f"HashAggregate spilled ({n.get('HashAgg Batches')} batches, {n.get('Disk Usage', 0)} kB on disk)",
                "Raise work_mem / hash_mem_multiplier for the reporting role, or pre-aggregate (materialized view, rollup table).",
                n.path,
                {"hashagg_batches": n.get("HashAgg Batches"), "disk_usage_kb": n.get("Disk Usage", 0)},
            )
        )


def _lossy_bitmap(n: PlanNode, out: list[Finding]) -> None:
    if n.node_type != "Bitmap Heap Scan":
        return
    lossy = int(n.get("Lossy Heap Blocks", 0) or 0)
    if lossy <= 0:
        return
    exact = int(n.get("Exact Heap Blocks", 0) or 0)
    rechecked = int(n.get("Rows Removed by Index Recheck", 0) or 0)
    out.append(
        Finding(
            "LOSSY_BITMAP",
            "medium",
            f"Bitmap on {n.relation} went lossy: {lossy:,} lossy vs {exact:,} exact blocks, "
            f"{rechecked:,} rows removed by recheck",
            "The bitmap exceeded work_mem and degraded to page granularity; raise work_mem for this query, or use "
            "a more selective (multi-column / partial) index so fewer pages qualify.",
            n.path,
            {"lossy_heap_blocks": lossy, "exact_heap_blocks": exact, "rows_removed_by_recheck": rechecked},
        )
    )


def analyse_plan(
    plan: Any,
    *,
    large_rows: int = LARGE_ROWS,
    loop_threshold: int = LOOP_THRESHOLD,
) -> ExplainReport:
    top, _ = _root(plan)
    root = parse_plan(plan)
    findings: list[Finding] = []
    stmts: list[str] = []
    nodes = list(walk(root))
    for n, limited in _with_limit_context(root):
        if n.node_type == "Seq Scan":
            _seq_scan(n, large_rows, findings, stmts)
        _index_filter(n, findings, stmts)
        _misestimate(n, limited, findings, stmts)
        _nested_loop(n, loop_threshold, findings, stmts)
        _hash_join_selective(n, large_rows, findings, stmts)
        _spills(n, findings)
        _lossy_bitmap(n, findings)
    hottest = sorted(nodes, key=lambda n: n.exclusive_ms, reverse=True)[:5]
    exec_ms = float(top.get("Execution Time", root.inclusive_ms))
    return ExplainReport(
        execution_time_ms=exec_ms,
        planning_time_ms=float(top.get("Planning Time", 0.0)),
        node_count=len(nodes),
        hottest_nodes=[
            {
                "path": n.path,
                "node_type": n.node_type,
                "relation": n.relation,
                "exclusive_ms": round(n.exclusive_ms, 2),
                "share": round(n.exclusive_ms / exec_ms, 4) if exec_ms else 0.0,
                "shared_read_blocks": int(n.get("Shared Read Blocks", 0) or 0),
            }
            for n in hottest
        ],
        findings=sort_findings(findings),
        statements=list(dict.fromkeys(stmts)),
    )
