"""Evals as monitoring, for systems that give a different answer every time.

There is no single correct output to diff against, so "working" is defined three ways and each is
measured continuously on (a sample of) production traffic:

1. **Property checks** — deterministic assertions every acceptable answer satisfies regardless of
   wording: required fields present, valid JSON, length bounds, cites a source, grounded in the
   retrieved context, no leaked secrets. These are the probabilistic SLI: *share of sampled outputs
   that pass*. SLO e.g. 97% over 28 days → burn-rate alerts exactly like an availability SLO.
2. **Behavioural baseline** — the distribution of steps, cost, tool mix and output length for a known
   good period. PSI against that baseline flags a changed agent (new model version, prompt edit,
   upstream data) before users notice — drift detection without ground truth.
3. **Golden set** — a fixed set of inputs re-run on every prompt/model change (offline gate) and on a
   schedule (online canary), scored with the same property checks.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from golden.agentops.guardrails import find_secrets
from golden.agentops.metrics import BEHAVIOR_PSI, EVAL_RESULTS
from golden.ai.drift import PSI_SIGNIFICANT, psi, psi_categorical

Check = Callable[[str, dict[str, Any]], bool]

_WORD = re.compile(r"[a-z0-9]{3,}")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def grounding_score(answer: str, context: str) -> float:
    """Share of the answer's content words that appear in the retrieved context (0–1)."""
    words = _tokens(answer)
    return len(words & _tokens(context)) / len(words) if words else 0.0


CHECKS: dict[str, Check] = {
    "non_empty": lambda out, ctx: bool(out.strip()),
    "within_length": lambda out, ctx: len(out) <= int(ctx.get("max_chars", 4000)),
    "valid_json": lambda out, ctx: _is_json(out),
    "has_required_fields": lambda out, ctx: _has_fields(out, ctx.get("required_fields", [])),
    "cites_source": lambda out, ctx: bool(re.search(r"\[\d+\]", out)),
    "grounded": lambda out, ctx: (
        grounding_score(out, ctx.get("context", "")) >= float(ctx.get("min_grounding", 0.6))
    ),
    "no_secrets": lambda out, ctx: not find_secrets(out),
    "no_refusal_when_answerable": lambda out, ctx: (
        not (
            ctx.get("answerable", True) and re.search(r"\b(i can(no|')t|unable to) (help|answer)", out, re.I)
        )
    ),
}


def _is_json(out: str) -> bool:
    try:
        json.loads(out)
        return True
    except ValueError:
        return False


def _has_fields(out: str, fields: Sequence[str]) -> bool:
    try:
        data = json.loads(out)
    except ValueError:
        return False
    return isinstance(data, dict) and all(f in data and data[f] not in (None, "") for f in fields)


@dataclass
class EvalResult:
    passed: bool
    checks: dict[str, bool]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate(
    output: str, checks: Sequence[str], context: dict[str, Any] | None = None, *, agent: str = "unknown"
) -> EvalResult:
    ctx = context or {}
    unknown = set(checks) - set(CHECKS)
    if unknown:
        raise KeyError(f"unknown eval checks {sorted(unknown)}; available: {sorted(CHECKS)}")
    results = {name: bool(CHECKS[name](output, ctx)) for name in checks}
    for name, ok in results.items():
        EVAL_RESULTS.labels(agent=agent, check=name, result="pass" if ok else "fail").inc()
    return EvalResult(all(results.values()), results, round(sum(results.values()) / max(1, len(results)), 3))


@dataclass
class BehaviorBaseline:
    """Snapshot of a known-good period of runs (from the run ledger)."""

    steps: list[float] = field(default_factory=list)
    cost_usd: list[float] = field(default_factory=list)
    results: list[str] = field(default_factory=list)

    @classmethod
    def from_runs(cls, runs: Sequence[dict[str, Any]]) -> BehaviorBaseline:
        return cls(
            steps=[float(r["steps"]) for r in runs],
            cost_usd=[float(r["cost_usd"]) for r in runs],
            results=[str(r["result"]) for r in runs],
        )

    def compare(self, runs: Sequence[dict[str, Any]], *, agent: str = "unknown") -> dict[str, Any]:
        current = BehaviorBaseline.from_runs(runs)
        scores = {
            "steps": psi(self.steps, current.steps),
            "cost_usd": psi(self.cost_usd, current.cost_usd),
            "results": psi_categorical(self.results, current.results),
        }
        for feature, value in scores.items():
            BEHAVIOR_PSI.labels(agent=agent, feature=feature).set(value)
        return {
            "psi": {k: round(v, 4) for k, v in scores.items()},
            "drifted": [k for k, v in scores.items() if v > PSI_SIGNIFICANT],
        }


def slo_status(passed: int, total: int, objective: float = 0.97) -> dict[str, Any]:
    """Probabilistic SLO: share of sampled outputs passing their property checks."""
    sli = passed / total if total else 1.0
    budget = 1 - objective
    burned = (1 - sli) / budget if budget else 0.0
    return {
        "sli": round(sli, 4),
        "objective": objective,
        "error_budget_burned": round(burned, 3),
        "breaching": sli < objective,
    }
