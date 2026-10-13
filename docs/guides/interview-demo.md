# Interview Demo: 10 Minutes

One rehearsed demo covering architecture, a live failure, governed remediation with human approval,
the audit trail, and recovery. Every command below runs against this repository as it is today. Every
number you quote comes from a command run on screen; nothing is asserted from slides.

**Setup (do it before the call):** `make bootstrap && make up && make up-observability`. Confirm that
`curl -s localhost:8000/health` returns `ok`. Open three windows: a terminal, Grafana
(<http://localhost:3000>), and the API docs (<http://localhost:8000/docs>).

For the approval step, start the platform in **supervised** mode:
`GOLDEN_AUTONOMY_MODE=supervised docker compose up -d`. In the default `dry_run` mode nothing
executes, which is safer but less interesting to watch.

## 0:00–1:30 · The shape of it

Open `README.md` → *Repository layout*, then say:

> "This is one template for enterprise modernization. `platform.yaml` is the only file an engineer
> edits, and every `make` target reads its defaults from it. One Python package and one container image
> run all the services. Each service gets health and readiness checks, Prometheus metrics, API keys,
> rate limiting, a non-root user and a read-only filesystem from a shared foundation, so no service
> has to remember to add them."

Point at `src/golden/services/common.py` (`create_app`), then at `deploy/terraform/live/` and
`deploy/helm/golden/` (one chart, with an overlay per cloud).

## 1:30–3:00 · It's running, and it's observable

```bash
docker compose ps                          # 14 services, all healthy
curl -s localhost:8091/metrics | grep golden_http_requests_total | head -3
make security-status                       # autonomy mode, kill switch, caps, audit chain
```

In Grafana, open *Golden Platform Overview*. Say that the SLO rules live in
`observability/prometheus/rules/slo_rules.yml` as multi-window burn-rate alerts, not as one-off
thresholds.

## 3:00–4:30 · Break something

```bash
curl -s -XPOST localhost:8092/ops/chaos/error -H 'content-type: application/json' -d '{"error_rate": 0.5}'
k6 run tools/k6/transaction-load.js        # or: for i in $(seq 200); do curl -s localhost:8092/health >/dev/null; done
```

Watch the payment-gateway error rate climb on the dashboard. If Alertmanager is running, `HighErrorRate`
fires. Say:

> "Chaos is built into the services: bounded (latency is capped at 10 seconds) and switchable
> (`GOLDEN_CHAOS_ENABLED=false`) so it can't be left on in production by mistake."

## 4:30–7:00 · Governed remediation: the part that matters

```bash
curl -s -XPOST localhost:8000/v1/decisions -H 'content-type: application/json' \
  -d '{"fraud_score": 0.97, "criticality": "high", "target": "acct-7781"}' | jq
```

Read out the response: `security.fraud` → risk `critical` → `SEV1` → recommended
`isolate_fraud_transactions` → outcome **`pending_approval`**. Then say:

> "The AI recommends; it doesn't act alone. Every action goes through the ActionGovernor: an allowlist,
> a blast-radius limit, rate caps and an autonomy mode. Critical actions *always* need a named human,
> in every mode."

```bash
curl -s localhost:8000/v1/actions/pending | jq '.pending[0]'
curl -s -XPOST localhost:8000/v1/actions/<request_id>/approve -H 'content-type: application/json' \
  -d '{"approver": "jane.doe"}' | jq '.outcome, .reason'          # "execute", "approved_by:jane.doe"
curl -s localhost:8000/v1/audit | jq '.chain_valid, .total'      # true, N
```

Explain the audit chain: each entry carries the SHA-256 hash of the previous one, so editing or
deleting a past entry breaks every hash after it. That's what `chain_valid` checks. The code is in
`src/golden/security/audit.py`.

Then show the kill switch:

```bash
GOLDEN_KILL_SWITCH=true docker compose up -d api && make security-status   # kill_switch_engaged: true
```

## 7:00–8:30 · Recover

```bash
curl -s -XPOST localhost:8092/ops/reset
GOLDEN_KILL_SWITCH=false docker compose up -d api
```

The error rate returns to baseline on the dashboard. Close the loop with:

> "Detection, decision, approval, action, audit, recovery: each step is a separate, testable component,
> and `make check` runs all of them in CI."

## 8:30–10:00 · Pick one depth slice for the role

| Role | Show | Command |
|---|---|---|
| Platform / cloud architect | IAM modernization: personas → permission sets, SCP/RCP guardrails, OPA gate on the plan | `make iam-model`, `make iam-policy-test`, `golden iam roles \| jq .summary` |
| SRE | Agent cost controls proven by switching them off | `make agent-verify`, `make agent-overnight` |
| Migration lead | VMware → OpenShift: assessment, waves, MTV manifests | `make migrate-assess`, `make migrate-plan` |
| AI / ML platform | Drift-triggered retrain, gated promotion that needs an approver | `golden model retrain --force`, `golden model promote 2 --approver you` (watch it refuse a weaker model) |
| Security | OWASP LLM Top 10 red-team gate, Envoy ext_authz | `make redteam`, `curl -XPOST localhost:8099/ext_authz/v1/messages -d '{"prompt":"ignore previous instructions"}'` |

## Questions you will get, and the honest answers

- **"Is this in production?"** "It's a template I built and run end to end locally and in CI, and I
  have deployed it to a dev account (`make deploy CLOUD=aws ENV=dev`)." Only say the deploy part
  after you've done it. The data is synthetic, and [CLAIMS.md](../CLAIMS.md) lists what is measured
  and what is a target.
- **"How did you measure that number?"** Quote only numbers you can reproduce on screen:
  - `make test` (test count and coverage);
  - `golden agent verify` / `overnight` (cost-control proofs);
  - `golden model retrain --force` (holdout recall, AUC and FP rate on synthetic data);
  - your own k6 and chaos runs.
- **"Why LSTM and TCN instead of a simpler baseline?"** The thresholds still decide on their own. The
  forecasters only add a `forecast_risk` flag, and without trained weights the analyzer falls back to
  a statistical forecast (`src/golden/ai/agents/analyzer.py`, `agent_config.yaml`). The honest gap: no
  published comparison against a seasonal-naive baseline yet. Say that, and say how you'd run it
  (`make train` plus the same holdout).
- **"What happens if OPA is down during a plan?"** The gate fails closed: no policy result means no
  apply. `scripts/iam-policy-gate.sh` exits non-zero when `opa` is missing.
- **"Why one image for all services?"** One build, one SBOM and one scan to keep patched, at the cost
  of a larger image and coupled releases. Splitting is a Helm values change, not a rewrite.

Rehearse the whole run against a timer until it fits in 10 minutes with a minute to spare. Record it
once for the website.
