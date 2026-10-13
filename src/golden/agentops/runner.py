"""Safe agent runner — the framework-agnostic wrapper every agent runs inside.

Agents (LangGraph, a hand-written tool loop, a Managed Agent client…) implement one method,
``next_step(state) -> Step``. The runner owns everything that keeps the agent safe to leave running:

identity & tool allowlist → drain signal → kill switch / pre-flight budget → step → cost & metrics →
checkpoint → per-run / per-day caps → loop detection → step ceiling → ledger + audit trail.

Results: ``success`` · ``looped`` · ``capped`` · ``ceiling`` · ``drained`` · ``blocked`` · ``killed`` · ``failed``.
"""

from __future__ import annotations

import os
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

import yaml

from golden.agentops.budget import Budget, BudgetExceeded
from golden.agentops.checkpoint import CheckpointStore, DrainSignal
from golden.agentops.guardrails import check_tool
from golden.agentops.ledger import RunLedger
from golden.agentops.loops import LoopDetector
from golden.agentops.metrics import (
    AGENT_COST,
    AGENT_LOOPS,
    AGENT_RUNS,
    AGENT_STEPS,
    AGENT_TOKENS,
    AGENT_WASTED,
)
from golden.agentops.pricing import Usage, cost_usd
from golden.security.audit import default_audit_log


def state_dir_default() -> Path:
    """Ledger / budget / checkpoint directory, resolved at call time (``GOLDEN_AGENTOPS_DIR``)."""
    return Path(os.getenv("GOLDEN_AGENTOPS_DIR", ".agentops"))


@dataclass
class AgentIdentity:
    name: str
    team: str
    owner: str = ""
    model: str = "simulated"
    allowed_tools: list[str] = field(default_factory=lambda: ["*"])
    per_run_usd: float = 0.50
    per_day_usd: float = 25.0
    on_breach: str = "drain"
    step_ceiling: int = 40
    success_definition: str = ""


@lru_cache(maxsize=4)
def _agents(path: str) -> dict[str, Any]:
    text = (
        Path(path).read_text(encoding="utf-8")
        if path
        else resources.files("golden.agentops").joinpath("agents.yaml").read_text("utf-8")
    )
    return (yaml.safe_load(text) or {}).get("agents", {})


def load_identity(name: str) -> AgentIdentity:
    agents = _agents(os.getenv("GOLDEN_AGENTS_FILE", ""))
    if name not in agents:
        raise KeyError(f"unknown agent {name!r}: register it in agents.yaml before it can run")
    return AgentIdentity(name=name, **agents[name])


def registered_agents() -> list[str]:
    return sorted(_agents(os.getenv("GOLDEN_AGENTS_FILE", "")))


@dataclass
class Step:
    action: str
    target: str
    usage: Usage
    model: str
    final: bool = False
    output: Any = None

    @property
    def signature(self) -> str:
        return f"{self.action}:{self.target}"


@dataclass
class RunState:
    task: dict[str, Any]
    completed: list[dict[str, Any]]


class AgentPolicy(Protocol):
    def next_step(self, state: RunState) -> Step: ...


@dataclass
class RunResult:
    run_id: str
    trace_id: str
    agent: str
    team: str
    task: str
    result: str
    reason: str
    steps: int
    cost_usd: float
    saved_by_checkpoint_usd: float
    duration_s: float
    spans: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SafeAgentRunner:
    def __init__(
        self,
        identity: AgentIdentity,
        *,
        state_dir: str | Path | None = None,
        caps: bool = True,
        loop_detection: bool = True,
        checkpoints: bool = True,
        step_estimate_usd: float = 0.01,
        drain: DrainSignal | None = None,
    ) -> None:
        self.identity = identity
        self.state_dir = Path(state_dir) if state_dir is not None else state_dir_default()
        self.caps, self.loop_detection, self.checkpoints = caps, loop_detection, checkpoints
        self.step_estimate_usd = step_estimate_usd
        self.drain = drain or DrainSignal()
        self.ledger = RunLedger(self.state_dir)
        self.store = CheckpointStore(self.state_dir, enabled=checkpoints)

    def run(self, policy: AgentPolicy, task: dict[str, Any], *, resume: bool = False) -> RunResult:
        ident = self.identity
        task_id = str(task.get("id", "task"))
        budget = Budget(
            ident.name,
            ident.per_run_usd,
            ident.per_day_usd,
            ident.on_breach,
            self.state_dir,
            enabled=self.caps,
        )
        detector = LoopDetector(enabled=self.loop_detection)
        state: dict[str, Any] = self.store.load(task_id) if resume else {"completed": [], "spent_usd": 0.0}
        completed: list[dict[str, Any]] = list(state["completed"])
        saved = float(state["spent_usd"]) if resume else 0.0
        seen = {c["target"] for c in completed}
        for c in completed:
            detector.observe(f"{c['action']}:{c['target']}", progress=True)

        run_id, trace_id = uuid.uuid4().hex[:8], uuid.uuid4().hex
        spans: list[dict[str, Any]] = []
        started = time.perf_counter()
        cost = 0.0
        result, reason = "ceiling", f"hit step ceiling ({ident.step_ceiling})"

        for _ in range(max(0, ident.step_ceiling - len(completed))):
            if self.drain.requested:
                result, reason = "drained", "drain requested (rollout/SIGTERM); checkpoint kept"
                break
            try:
                budget.preflight(self.step_estimate_usd)
            except BudgetExceeded as exc:
                result, reason = self._breach(budget, exc)
                break

            t0 = time.perf_counter()
            step = policy.next_step(RunState(task, completed))
            tool = check_tool(step.action, [*ident.allowed_tools, "final"])
            if not tool.allowed:
                result, reason = "blocked", tool.reasons[0]
                break
            usd = cost_usd(step.model, step.usage)
            cost += usd
            self._record_step(step, usd)
            progress = step.target not in seen and step.action != "explore"
            seen.add(step.target)
            completed.append({"action": step.action, "target": step.target, "usd": usd})
            self.store.save(task_id, {"completed": completed, "spent_usd": saved + cost})
            spans.append(
                {
                    "span_id": uuid.uuid4().hex[:16],
                    "trace_id": trace_id,
                    "name": step.signature,
                    "model": step.model,
                    "tokens_in": step.usage.input_tokens,
                    "tokens_out": step.usage.output_tokens,
                    "cost_usd": round(usd, 6),
                    "duration_ms": round(1000 * (time.perf_counter() - t0), 2),
                }
            )
            if step.final:
                budget.run_spend += usd  # done is done; still counted toward the day
                budget._write_day(budget.day_spend() + usd)
                result, reason = "success", ident.success_definition or "final step reached"
                break
            try:
                budget.charge(usd)
            except BudgetExceeded as exc:
                result, reason = self._breach(budget, exc)
                break
            if loop := detector.observe(step.signature, progress=progress):
                AGENT_LOOPS.labels(agent=ident.name, kind=loop).inc()
                result, reason = "looped", f"loop detected: {loop} ({step.signature})"
                break

        if result == "success" or (result == "capped" and ident.on_breach == "stop"):
            self.store.clear(task_id)
        AGENT_RUNS.labels(agent=ident.name, team=ident.team, result=result).inc()
        if result != "success":
            AGENT_WASTED.labels(agent=ident.name, team=ident.team).inc(cost)
        record = RunResult(
            run_id=run_id,
            trace_id=trace_id,
            agent=ident.name,
            team=ident.team,
            task=task_id,
            result=result,
            reason=reason,
            steps=len(spans),
            cost_usd=round(cost, 6),
            saved_by_checkpoint_usd=round(saved, 6),
            duration_s=round(time.perf_counter() - started, 3),
            spans=spans,
        )
        self.ledger.append(
            {
                **{k: v for k, v in record.to_dict().items() if k != "spans"},
                "ts": datetime.now(UTC).isoformat(),
                "model": ident.model,
                "owner": ident.owner,
                "caps": self.caps,
                "loop_detection": self.loop_detection,
            }
        )
        default_audit_log().record(
            "agent.run",
            {"run_id": run_id, "task": task_id, "result": result, "cost_usd": record.cost_usd},
            actor=ident.name,
        )
        return record

    def _record_step(self, step: Step, usd: float) -> None:
        ident = self.identity
        AGENT_STEPS.labels(agent=ident.name, team=ident.team).inc()
        AGENT_COST.labels(agent=ident.name, team=ident.team, model=step.model).inc(usd)
        AGENT_TOKENS.labels(agent=ident.name, team=ident.team, model=step.model, direction="input").inc(
            step.usage.input_tokens
        )
        AGENT_TOKENS.labels(agent=ident.name, team=ident.team, model=step.model, direction="output").inc(
            step.usage.output_tokens
        )

    @staticmethod
    def _breach(budget: Budget, exc: BudgetExceeded) -> tuple[str, str]:
        action = budget.breach(exc)
        result = "killed" if action == "kill" else "capped"
        return result, f"{exc} → {action}"


# ----------------------------------------------------------------------------- reference agent
class SimulatedTaskAgent:
    """Deterministic stand-in for an LLM tool loop. ``task['shape']`` picks the behaviour:

    ``converging`` (finishes in 6 steps) · ``bouncing`` (A,B,A,B…) · ``stuck`` (same call forever) ·
    ``drifting`` (explores new fields forever).
    """

    CONVERGING = [
        ("read", "input"),
        ("parse", "amount"),
        ("validate", "amount"),
        ("lookup", "vendor"),
        ("write", "record"),
    ]

    def __init__(self, model: str = "simulated") -> None:
        self.model = model

    def next_step(self, state: RunState) -> Step:
        task, n = state.task, len(state.completed)
        rng = random.Random(f"{task.get('seed', 7)}:{n}")
        usage = Usage(input_tokens=rng.randint(1200, 1900), output_tokens=rng.randint(280, 520))
        shape = task.get("shape", "converging")
        if shape == "converging":
            if n < len(self.CONVERGING):
                action, target = self.CONVERGING[n]
                return Step(action, target, usage, self.model)
            return Step("write", "record", usage, self.model, final=True)
        if shape == "bouncing":
            return Step(*(("parse", "amount") if n % 2 == 0 else ("validate", "amount")), usage, self.model)
        if shape == "stuck":
            return Step("parse", "amount", usage, self.model)
        return Step("explore", f"field_{n}", usage, self.model)


SAMPLE_TASKS = {
    "good": {"id": "invoice-4471", "shape": "converging", "seed": 7},
    "malformed": {"id": "invoice-9902", "shape": "bouncing", "seed": 13},
    "stuck": {"id": "invoice-9903", "shape": "stuck", "seed": 3},
    "drifting": {"id": "invoice-9904", "shape": "drifting", "seed": 21},
}
