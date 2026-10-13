"""Executor agent — runs planned actions, but only those the ActionGovernor allows."""

from __future__ import annotations

import logging
from typing import Any

from golden.ai.remediation import execute_action
from golden.security.actions import ActionGovernor, Outcome, default_governor

logger = logging.getLogger(__name__)


class ExecutorAgent:
    def __init__(self, config: dict[str, Any] | None = None, governor: ActionGovernor | None = None) -> None:
        self.config = config or {}
        self.governor = governor or default_governor()
        self.max_actions_per_batch = int(self.config.get("safety", {}).get("max_actions_per_batch", 3))

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        actions = plan.get("planned_actions", [])
        report: dict[str, Any] = {
            "status": "completed",
            "total_actions": len(actions),
            "executed": [],
            "simulated": [],
            "pending_approval": [],
            "blocked": [],
            "failed": [],
        }
        if not actions:
            report["status"] = "skipped"
            return report

        for index, item in enumerate(actions):
            name = item["action"] if isinstance(item, dict) else str(item)
            params = item.get("params", {}) if isinstance(item, dict) else {}
            if index >= self.max_actions_per_batch:
                report["blocked"].append({"action": name, "reason": "batch_cap"})
                continue

            verdict = self.governor.evaluate(name, params, actor="executor")
            entry = {"action": name, "request_id": verdict.request_id, "reason": verdict.reason}
            if verdict.outcome is Outcome.EXECUTE:
                (
                    report["executed"]
                    if execute_action({"action": name, "params": params})
                    else report["failed"]
                ).append(entry)
            elif verdict.outcome is Outcome.SIMULATE:
                report["simulated"].append(entry)
            elif verdict.outcome is Outcome.PENDING_APPROVAL:
                report["pending_approval"].append(entry)
            else:
                report["blocked"].append(entry)

        if report["failed"]:
            report["status"] = "partial_failure" if report["executed"] else "failed"
        elif report["pending_approval"]:
            report["status"] = "awaiting_approval"
        elif report["blocked"] and not report["executed"] and not report["simulated"]:
            report["status"] = "blocked"
        return report
