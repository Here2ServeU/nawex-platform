"""Append-only run ledger and the unit economics finance actually asks about.

One JSON line per run. The report answers: what did we spend, what did it buy (cost per *successful*
task — failures stay in the numerator), how much was wasted on runs that failed (the failed-run tax),
and how much checkpoints saved.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


class RunLedger:
    def __init__(self, state_dir: str | Path = ".agentops") -> None:
        self.path = Path(state_dir) / "runs.jsonl"

    def append(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()
        ]


def unit_economics(records: list[dict[str, Any]]) -> dict[str, Any]:
    runs = len(records)
    successes = sum(1 for r in records if r["result"] == "success")
    spend = sum(float(r["cost_usd"]) for r in records)
    failed = [r for r in records if r["result"] != "success"]
    failed_spend = sum(float(r["cost_usd"]) for r in failed)
    per_request = spend / runs if runs else 0.0
    per_success = spend / successes if successes else None
    by_result: dict[str, float] = defaultdict(float)
    by_team: dict[str, float] = defaultdict(float)
    by_agent: dict[str, float] = defaultdict(float)
    for r in records:
        by_result[r["result"]] += float(r["cost_usd"])
        by_team[r.get("team", "")] += float(r["cost_usd"])
        by_agent[r.get("agent", "")] += float(r["cost_usd"])
    return {
        "runs": runs,
        "succeeded": successes,
        "failed": runs - successes,
        "spend_usd": round(spend, 6),
        "cost_per_request_usd": round(per_request, 6),
        "cost_per_successful_task_usd": round(per_success, 6) if per_success is not None else None,
        "success_cost_gap_pct": round((per_success / per_request - 1) * 100, 1)
        if per_success and per_request
        else None,
        "failed_run_tax_usd": round(failed_spend, 6),
        "failed_run_tax_pct": round(100 * failed_spend / spend, 1) if spend else 0.0,
        "saved_by_checkpoints_usd": round(
            sum(float(r.get("saved_by_checkpoint_usd", 0)) for r in records), 6
        ),
        "wasted_by_result_usd": {k: round(v, 6) for k, v in sorted(by_result.items()) if k != "success"},
        "spend_by_team_usd": {k: round(v, 6) for k, v in sorted(by_team.items())},
        "spend_by_agent_usd": {k: round(v, 6) for k, v in sorted(by_agent.items())},
    }
