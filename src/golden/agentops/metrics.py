"""Prometheus metrics for agent operations: cost, tokens, runs, loops, guardrails, evals.

The run id is deliberately never a label (unbounded cardinality); attribution is agent × team × model.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

AGENT_COST = Counter("golden_agent_cost_usd_total", "LLM spend in USD.", ["agent", "team", "model"])
AGENT_TOKENS = Counter("golden_agent_tokens_total", "LLM tokens.", ["agent", "team", "model", "direction"])
AGENT_STEPS = Counter("golden_agent_steps_total", "Agent steps executed.", ["agent", "team"])
AGENT_RUNS = Counter("golden_agent_runs_total", "Agent runs by result.", ["agent", "team", "result"])
AGENT_WASTED = Counter(
    "golden_agent_wasted_usd_total", "Spend on runs that did not succeed.", ["agent", "team"]
)
AGENT_LOOPS = Counter("golden_agent_loops_detected_total", "Loops caught.", ["agent", "kind"])
AGENT_BUDGET_BREACHES = Counter(
    "golden_agent_budget_breaches_total", "Budget cap hits.", ["agent", "scope", "action"]
)
AGENT_DAY_SPEND = Gauge("golden_agent_day_spend_usd", "Spend so far today.", ["agent"])
LLM_CALLS = Counter("golden_llm_calls_total", "LLM gateway calls by outcome.", ["model", "status"])
LLM_LATENCY = Histogram(
    "golden_llm_latency_seconds",
    "LLM call latency.",
    ["model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)
GUARD_DECISIONS = Counter(
    "golden_llm_guard_decisions_total", "LLM guardrail decisions.", ["stage", "decision", "category"]
)
EVAL_RESULTS = Counter("golden_agent_eval_total", "Online eval outcomes.", ["agent", "check", "result"])
BEHAVIOR_PSI = Gauge("golden_agent_behavior_psi", "PSI of agent behaviour vs baseline.", ["agent", "feature"])
REDTEAM_PASS_RATE = Gauge("golden_llm_redteam_pass_rate", "Share of red-team probes defended.", ["target"])
