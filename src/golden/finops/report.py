"""One-call FinOps summary over FOCUS data: the Inform / Optimize / Operate views together.

``finops_report()`` with no arguments runs on :func:`~golden.finops.focus.sample_focus_data` and the
sample utilization, compute spend and cluster, so the CLI and demos work offline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from golden.finops.allocation import (
    DEFAULT_REQUIRED_TAGS,
    Method,
    breakdown,
    chargeback,
    showback,
    tag_coverage,
)
from golden.finops.allocation import unit_economics as unit_costs
from golden.finops.anomalies import budget_status, detect_anomalies, forecast_month_end
from golden.finops.focus import load_focus, sample_focus_data
from golden.finops.recommendations import (
    allocate_cluster_cost,
    commitment_recommendation,
    rightsizing,
    sample_cluster,
    sample_hourly_compute_spend,
    sample_utilization,
)

SAMPLE_BUDGETS = {"total": 120_000.0, "payments": 24_000.0, "search": 18_000.0, "ml": 30_000.0}
SAMPLE_USAGE = {"payments": 41_500_000, "search": 260_000_000, "total": 310_000_000}


def finops_report(
    source: str | Path | pd.DataFrame | None = None,
    *,
    key: str = "Team",
    budgets: Mapping[str, float] | None = None,
    usage: Mapping[str, float] | None = None,
    unit: str = "transactions",
    method: Method = "proportional",
    required_tags: Sequence[str] = DEFAULT_REQUIRED_TAGS,
    as_of: date | None = None,
    include_samples: bool | None = None,
) -> dict[str, Any]:
    """Coverage, showback, chargeback, breakdowns, unit economics, anomalies, forecast, budgets and
    (with ``include_samples``, default on for sample data) recommendations and Kubernetes allocation."""
    sample = source is None
    frame = sample_focus_data() if source is None else load_focus(source)
    budgets = SAMPLE_BUDGETS if budgets is None and sample else (budgets or {})
    usage = SAMPLE_USAGE if usage is None and sample else (usage or {})
    with_samples = sample if include_samples is None else include_samples

    shown = showback(frame, key, method=method)
    charged = chargeback(frame, key, method=method)
    report: dict[str, Any] = {
        "period": {
            "start": frame["ChargePeriodStart"].min().date().isoformat() if not frame.empty else None,
            "end": frame["ChargePeriodStart"].max().date().isoformat() if not frame.empty else None,
        },
        "total_cost": round(float(frame["EffectiveCost"].sum()), 2),
        "tag_coverage": tag_coverage(frame, required_tags).to_dict(),
        "showback": shown.to_dict(),
        "chargeback": charged.to_dict(),
        "by_provider": _records(breakdown(frame, "ProviderName")),
        "by_service": _records(breakdown(frame, ["ProviderName", "ServiceName"]).head(15)),
        "unit_economics": [u.to_dict() for u in unit_costs(charged, usage, unit=unit)],
        "anomalies": {
            "by_service": [a.to_dict() for a in detect_anomalies(frame, "ServiceName")],
            "by_team": [a.to_dict() for a in detect_anomalies(frame, key)],
        },
        "forecast": forecast_month_end(frame, as_of).to_dict() if not frame.empty else None,
        "budgets": [b.to_dict() for b in budget_status(frame, budgets, key, as_of)] if budgets else [],
    }
    if with_samples:
        nodes, pods = sample_cluster()
        commitment = commitment_recommendation(sample_hourly_compute_spend())
        report["recommendations"] = [r.to_dict() for r in rightsizing(sample_utilization())] + (
            [commitment.to_dict()] if commitment else []
        )
        report["kubernetes"] = allocate_cluster_cost(nodes, pods).to_dict()
    return report


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    out = frame.copy()
    out["EffectiveCost"] = out["EffectiveCost"].round(2)
    out["share"] = out["share"].round(4)
    return [{str(k): v for k, v in row.items()} for row in out.to_dict(orient="records")]
