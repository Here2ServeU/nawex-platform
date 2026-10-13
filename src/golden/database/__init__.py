"""Database performance & optimization: workload, EXPLAIN, index/vacuum and capacity/cost advisors.

PostgreSQL first (Aurora PostgreSQL / RDS / self-managed), with MySQL notes where the concept differs.
Everything is a pure function over exported statistics — no live database connection is required, so
the advisors run in CI, on a laptop, or against a snapshot attached to an incident.
"""

from golden.database.capacity import (
    CapacityReport,
    PoolSizing,
    ReadScalingPlan,
    RightsizingResult,
    assess_capacity,
    load_price_table,
    memory_parameters,
    partitioning_plan,
    pool_sizing,
    read_scaling,
    rightsize,
)
from golden.database.explain import (
    ExplainReport,
    PlanNode,
    analyse_plan,
    filter_columns,
    load_plan,
    parse_plan,
)
from golden.database.findings import Finding, severity_counts, sort_findings
from golden.database.indexes import (
    IndexDef,
    IndexReport,
    TableHealth,
    analyse_indexes,
    autovacuum_settings,
    parse_indexdef,
)
from golden.database.samples import (
    sample_capacity_profile,
    sample_explain_plans,
    sample_index_snapshot,
    sample_statements,
)
from golden.database.workload import (
    QueryStat,
    WorkloadReport,
    analyse_workload,
    fingerprint,
    load_statements,
    parse_statements,
)

__all__ = [
    "CapacityReport",
    "ExplainReport",
    "Finding",
    "IndexDef",
    "IndexReport",
    "PlanNode",
    "PoolSizing",
    "QueryStat",
    "ReadScalingPlan",
    "RightsizingResult",
    "TableHealth",
    "WorkloadReport",
    "analyse_indexes",
    "analyse_plan",
    "analyse_workload",
    "assess_capacity",
    "autovacuum_settings",
    "filter_columns",
    "fingerprint",
    "load_plan",
    "load_price_table",
    "load_statements",
    "memory_parameters",
    "parse_indexdef",
    "parse_plan",
    "parse_statements",
    "partitioning_plan",
    "pool_sizing",
    "read_scaling",
    "rightsize",
    "sample_capacity_profile",
    "sample_explain_plans",
    "sample_index_snapshot",
    "sample_statements",
    "severity_counts",
    "sort_findings",
]
