"""Planner agent — maps detected risks to remediation actions using the rule catalog."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from golden.ai.remediation import load_rules

logger = logging.getLogger(__name__)

_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class PlannerAgent:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.rules = load_rules()["rules"]

    def _match(self, risk_type: str, level: str) -> dict[str, Any] | None:
        candidates = [r for r in self.rules if r.get("trigger") == risk_type]
        # exact level first, then the strongest rule whose level does not exceed the observed level
        for rule in candidates:
            if rule.get("level") == level:
                return {
                    "action": rule["action"],
                    "params": dict(rule.get("params", {})),
                    "rule_id": rule.get("id"),
                }
        eligible = [
            r for r in candidates if _LEVEL_ORDER.get(r.get("level", ""), 9) <= _LEVEL_ORDER.get(level, -1)
        ]
        if eligible:
            rule = max(eligible, key=lambda r: _LEVEL_ORDER[r["level"]])
            return {
                "action": rule["action"],
                "params": dict(rule.get("params", {})),
                "rule_id": rule.get("id"),
            }
        if "latency" in risk_type and level in {"high", "critical"}:
            return {"action": "scale_up_replicas", "params": {}, "rule_id": "default-latency"}
        if risk_type == "capacity_trend_risk":
            return {"action": "scale_up_replicas", "params": {}, "rule_id": "default-capacity-trend"}
        if risk_type in {"cpu_risk", "memory_risk"}:
            return {"action": "optimize_resources", "params": {}, "rule_id": "default-capacity"}
        if "error" in risk_type:
            return {"action": "restart_service", "params": {}, "rule_id": "default-errors"}
        return None

    def plan(self, analysis: dict[str, Any]) -> dict[str, Any]:
        plan_id = datetime.now(UTC).strftime("plan-%Y%m%dT%H%M%S%f")
        if not analysis or analysis.get("status") == "healthy":
            return {"plan_id": plan_id, "status": "no_action_needed", "planned_actions": []}

        actions, reasoning = [], []
        for risk_type, level in analysis.get("risk_flags", {}).items():
            if not risk_type.endswith("_risk") or not isinstance(level, str):
                continue
            match = self._match(risk_type, level)
            if match:
                actions.append(match)
                reasoning.append(f"{match['action']} mitigates {risk_type} ({level}) via {match['rule_id']}")
            else:
                reasoning.append(f"manual review required for {risk_type} ({level})")
        return {
            "plan_id": plan_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "status": "actions_planned" if actions else "manual_review_required",
            "planned_actions": actions,
            "reasoning": reasoning,
            "analysis_reference": analysis.get("timestamp"),
        }
