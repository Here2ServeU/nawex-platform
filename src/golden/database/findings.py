"""Shared finding model for the database optimization advisors.

Every advisor (workload, explain, indexes, capacity) returns explainable :class:`Finding` objects: a
stable ``code``, a ``severity``, a human message, a concrete remediation (usually a SQL statement or a
parameter change) and the ``evidence`` numbers that triggered the rule, so a reviewer can re-derive the
conclusion without trusting the tool.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low", "info")
_RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass
class Finding:
    code: str
    severity: str  # critical | high | medium | low | info
    message: str
    remediation: str
    target: str = ""  # queryid, relation, table or instance the finding is about
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in _RANK:
            raise ValueError(f"unknown severity {self.severity!r}; expected one of {SEVERITIES}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Most severe first; stable within a severity (rule order is preserved)."""
    return sorted(findings, key=lambda f: _RANK[f.severity])


def severity_counts(findings: Iterable[Finding]) -> dict[str, int]:
    counts = Counter(f.severity for f in findings)
    return {s: counts.get(s, 0) for s in SEVERITIES}


def quote_ident(name: str) -> str:
    """Quote an identifier only when needed (keeps generated DDL readable)."""
    if name.replace("_", "a").isalnum() and name == name.lower() and not name[:1].isdigit():
        return name
    return '"' + name.replace('"', '""') + '"'


def index_name(table: str, columns: Iterable[str], prefix: str = "idx") -> str:
    """Deterministic index name ``idx_<table>_<cols>`` trimmed to PostgreSQL's 63-byte NAMEDATALEN."""
    base = table.split(".")[-1]
    cols = "_".join(c.replace("(", "_").replace(")", "").replace(" ", "") for c in columns)
    return f"{prefix}_{base}_{cols}"[:63].rstrip("_")
