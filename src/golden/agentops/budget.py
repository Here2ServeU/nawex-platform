"""Dollar budgets with three enforcement points and a decided-in-advance breach action.

Gates (checked in this order on every step):

1. **pre-flight** — before calling the model: would the *estimated* step cost cross the per-run cap?
   Stops the run before money is spent.
2. **per-run**   — after charging the step's actual cost: has this run reached its cap?
3. **per-day**   — after charging: has this agent reached its daily cap? Persisted to disk so a restart
   (or a fleet of workers sharing a volume) cannot reset it.

The platform kill switch (``GOLDEN_KILL_SWITCH``) is checked first and wins over everything.

``on_breach`` is chosen when the agent is configured, not at 3am:

* ``drain`` — finish the current step, keep the checkpoint, exit cleanly; resumable tomorrow.
* ``stop``  — exit immediately and discard the checkpoint (the work is not worth resuming).
* ``kill``  — engage the platform kill switch file so *every* agent and autonomous action halts.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from golden.agentops.metrics import AGENT_BUDGET_BREACHES, AGENT_DAY_SPEND
from golden.config import get_settings
from golden.security import killswitch

BREACH_ACTIONS = ("drain", "stop", "kill")


class BudgetExceeded(RuntimeError):
    def __init__(self, scope: str, spent: float, cap: float) -> None:
        super().__init__(f"{scope} budget exceeded: ${spent:.4f} >= ${cap:.4f}")
        self.scope, self.spent, self.cap = scope, spent, cap


@dataclass
class Budget:
    agent: str
    per_run_usd: float = 0.50
    per_day_usd: float = 25.0
    on_breach: str = "drain"
    state_dir: str | Path = ".agentops"
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.on_breach not in BREACH_ACTIONS:
            raise ValueError(f"on_breach must be one of {BREACH_ACTIONS}")
        self.state_dir = Path(self.state_dir)
        self.run_spend = 0.0

    # --- persistence ------------------------------------------------------------------------------
    def _day_file(self) -> Path:
        return Path(self.state_dir) / f"day-{self.agent}-{datetime.now(UTC).date().isoformat()}.json"

    def day_spend(self) -> float:
        f = self._day_file()
        return float(json.loads(f.read_text())["usd"]) if f.exists() else 0.0

    def _write_day(self, usd: float) -> None:
        f = self._day_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"usd": round(usd, 8)}))
        tmp.replace(f)
        AGENT_DAY_SPEND.labels(agent=self.agent).set(usd)

    # --- gates ------------------------------------------------------------------------------------
    def preflight(self, estimate_usd: float) -> None:
        if killswitch.is_engaged():
            raise BudgetExceeded("kill-switch", self.run_spend, 0.0)
        if self.enabled and self.run_spend + estimate_usd >= self.per_run_usd:
            raise BudgetExceeded("pre-flight", self.run_spend + estimate_usd, self.per_run_usd)

    def charge(self, usd: float) -> None:
        """Always record the money (even when caps are disabled), then enforce."""
        self.run_spend += usd
        day = self.day_spend() + usd
        self._write_day(day)
        if not self.enabled:
            return
        if self.run_spend >= self.per_run_usd:
            raise BudgetExceeded("per-run", self.run_spend, self.per_run_usd)
        if day >= self.per_day_usd:
            raise BudgetExceeded("per-day", day, self.per_day_usd)

    def breach(self, exc: BudgetExceeded) -> str:
        """Apply the configured breach action; returns the action taken."""
        action = "kill" if exc.scope == "kill-switch" else self.on_breach
        AGENT_BUDGET_BREACHES.labels(agent=self.agent, scope=exc.scope, action=action).inc()
        if action == "kill" and exc.scope != "kill-switch":
            path = get_settings().kill_switch_file or os.getenv("GOLDEN_KILL_SWITCH_FILE", "")
            if path:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(f"engaged by agent budget breach: {exc}\n")
        return action
