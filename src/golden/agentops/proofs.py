"""Prove every cost control by running it with the mechanism off, then on ("safe to leave overnight").

Each proof uses the offline simulated agent, so it is free, deterministic and runs in CI
(``golden agent verify``). Asserting a control in a comment is not evidence; turning it off and
watching the bill grow is.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from golden.agentops.ledger import RunLedger, unit_economics
from golden.agentops.pricing import Usage, cost_usd
from golden.agentops.runner import (
    SAMPLE_TASKS,
    AgentIdentity,
    SafeAgentRunner,
    SimulatedTaskAgent,
    load_identity,
)

MONTHLY_BUDGET_USD = 300.0


def overnight_projection(
    *, sec_per_step: float = 3.0, workers: int = 12, hours: float = 9.5, sample_steps: int = 300
) -> dict[str, Any]:
    """'The two numbers': what an unguarded looping fleet costs overnight vs one guarded run."""
    with tempfile.TemporaryDirectory() as tmp:
        ident = replace(load_identity("invoice-reader"), step_ceiling=sample_steps)
        runaway = SafeAgentRunner(
            ident, state_dir=tmp, caps=False, loop_detection=False, checkpoints=False
        ).run(SimulatedTaskAgent(), SAMPLE_TASKS["malformed"])
        per_step = runaway.cost_usd / max(1, runaway.steps)
        guarded = SafeAgentRunner(load_identity("invoice-reader"), state_dir=Path(tmp) / "g").run(
            SimulatedTaskAgent(), SAMPLE_TASKS["malformed"]
        )
    overnight = per_step * (3600 / sec_per_step) * workers * hours
    return {
        "cost_per_step_usd": round(per_step, 5),
        "unguarded_overnight_usd": round(overnight, 2),
        "guarded_run_usd": guarded.cost_usd,
        "guarded_result": guarded.result,
        "bill_that_never_arrived_usd": round(overnight - guarded.cost_usd, 2),
        "assumptions": {"sec_per_step": sec_per_step, "workers": workers, "hours": hours},
    }


def verify_controls() -> dict[str, Any]:
    proofs: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        base = load_identity("invoice-reader")

        def runner(name: str, ident: AgentIdentity = base, **kw: Any) -> SafeAgentRunner:
            return SafeAgentRunner(ident, state_dir=Path(tmp) / name, **kw)

        # 1. cost is visible: priced from the rate card, recorded per run
        good = runner("visible").run(SimulatedTaskAgent(), SAMPLE_TASKS["good"])
        proofs["1_cost_visible"] = {
            "ok": good.cost_usd > 0 and abs(cost_usd("simulated", Usage(1_000_000, 0)) - 2.0) < 1e-9,
            "run_cost_usd": good.cost_usd,
        }
        # 2. the cap alone stops a loop (loop detection off)
        capped_ident = replace(base, per_run_usd=0.05)
        capped = runner("cap", capped_ident, loop_detection=False).run(
            SimulatedTaskAgent(), SAMPLE_TASKS["malformed"]
        )
        proofs["2_cap_stops_runaway"] = {
            "ok": capped.result == "capped" and capped.cost_usd <= 0.06,
            "cost_usd": capped.cost_usd,
        }
        # 3. loop detection stops it sooner than the agent's real cap would
        cap_only = runner("cap-only", loop_detection=False).run(
            SimulatedTaskAgent(), SAMPLE_TASKS["malformed"]
        )
        looped = runner("loop").run(SimulatedTaskAgent(), SAMPLE_TASKS["malformed"])
        proofs["3_loop_detection_cheaper"] = {
            "ok": looped.result == "looped" and looped.cost_usd < cap_only.cost_usd,
            "looped_usd": looped.cost_usd,
            "cap_only_usd": cap_only.cost_usd,
        }
        # 4. checkpoints: a killed run resumes without paying twice
        short = replace(base, step_ceiling=3)
        killed = runner("ckpt", short).run(SimulatedTaskAgent(), SAMPLE_TASKS["good"])
        resumed = runner("ckpt").run(SimulatedTaskAgent(), SAMPLE_TASKS["good"], resume=True)
        proofs["4_checkpoint_resume"] = {
            "ok": killed.result == "ceiling"
            and resumed.result == "success"
            and resumed.saved_by_checkpoint_usd >= 0.99 * killed.cost_usd,
            "saved_usd": resumed.saved_by_checkpoint_usd,
        }
        # 5. cost per successful task is the honest number (failures stay in the numerator)
        batch = runner("batch")
        for _ in range(6):
            batch.run(SimulatedTaskAgent(), SAMPLE_TASKS["good"])
        for _ in range(4):
            batch.run(SimulatedTaskAgent(), SAMPLE_TASKS["malformed"])
        econ = unit_economics(RunLedger(Path(tmp) / "batch").records())
        proofs["5_cost_per_success"] = {
            "ok": econ["cost_per_successful_task_usd"] > econ["cost_per_request_usd"]
            and econ["failed_run_tax_usd"] > 0,
            "cost_per_request_usd": econ["cost_per_request_usd"],
            "cost_per_successful_task_usd": econ["cost_per_successful_task_usd"],
            "failed_run_tax_pct": econ["failed_run_tax_pct"],
        }
        # 6. with everything off, the projection blows through the monthly budget
        naked = runner(
            "naked", replace(base, step_ceiling=300), caps=False, loop_detection=False, checkpoints=False
        ).run(SimulatedTaskAgent(), SAMPLE_TASKS["malformed"])
        projected_month = naked.cost_usd / naked.steps * (3600 / 3.0) * 24 * 30
        proofs["6_unguarded_exceeds_budget"] = {
            "ok": naked.result == "ceiling" and projected_month > 2 * MONTHLY_BUDGET_USD,
            "projected_monthly_usd": round(projected_month, 2),
        }
    return {"passed": all(p["ok"] for p in proofs.values()), "proofs": proofs}
