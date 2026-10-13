# Runbook: Runaway Agent Spend

| | |
|---|---|
| **Alerts** | `AgentBurnRateFast` (page), `AgentBudgetKill` (page), `AgentLoopStorm`, `AgentBurnRateSlow`, `AgentFailedRunTaxHigh` |
| **Dashboard** | Grafana → *Golden Platform — Agent Operations* |
| **Owner** | Agent's owning team (`agents.yaml` → `owner`), platform on-call (escalation) |

## 1. Stop the bleeding (first 5 minutes)

1. Find who is spending, from the dashboard (*Who is spending it?*) or with:
   `topk(5, sum by (agent, team) (rate(golden_agent_cost_usd_total[15m])))`.
2. If the spend is not self-limiting (loops are not being caught and caps are not firing), **engage the
   kill switch**. It halts every agent and every autonomous action. Detection and recommendations keep
   running.

   ```bash
   kubectl -n golden exec deploy/golden-agent-ops -- touch "$GOLDEN_KILL_SWITCH_FILE"   # or set GOLDEN_KILL_SWITCH=true
   golden security status                                                                 # confirm: engaged
   ```

3. If only one agent is affected, lower its `per_run_usd` / `per_day_usd` in `agents.yaml` and deploy.
   Prefer that over the global switch.

## 2. Diagnose

- `golden agent report` shows spend by agent and result. A high `looped` share means loops are being
  caught and something upstream changed. A high `capped` or `ceiling` share means loops are *not* being
  caught.
- Look at the ledger lines and trace spans for the agent. Repeated `type:target` signatures point to a
  tool returning the same error. New targets every step point to a drifting exploration.
- Check what changed: model version, prompt, tool behaviour, input shape. Compare
  `golden_agent_behavior_psi`.

## 3. Recover

1. Fix the cause: the prompt, the tool's error handling, or a tighter `step_ceiling`.
2. Run `golden agent verify` (proofs still pass) and `golden agent redteam`.
3. Release the kill switch (`rm "$GOLDEN_KILL_SWITCH_FILE"`). Drained runs resume from their
   checkpoints with `--resume` and don't pay twice.
4. Record the incident's spend (`saved_by_checkpoint_usd`, the overnight projection avoided) in the
   weekly cost review.
