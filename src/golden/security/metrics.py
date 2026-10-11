"""Prometheus metrics for the AI-safety layer (registered once per process)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge

GUARDRAIL_REJECTIONS = Counter(
    "golden_guardrail_rejections_total",
    "Inputs rejected by AI guardrails.",
    ["service", "reason"],
)
ACTIONS_BLOCKED = Counter(
    "golden_actions_blocked_total",
    "Autonomous actions blocked by the action governor.",
    ["reason"],
)
ACTIONS_EXECUTED = Counter(
    "golden_actions_executed_total",
    "Autonomous actions allowed to execute.",
    ["action", "mode"],
)
KILL_SWITCH = Gauge("golden_kill_switch_engaged", "1 when the autonomy kill switch is engaged.")
RATE_LIMITED = Counter("golden_rate_limited_total", "Requests rejected by rate limiting.", ["service"])
AUTH_FAILURES = Counter(
    "golden_auth_failures_total", "Requests rejected for a missing/invalid API key.", ["service"]
)
