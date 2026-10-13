# Agent Operations — Running AI Agents in Production

Most teams can build an agent. This part of the platform is about running one: what it costs, whether
it's behaving, who is allowed to run it, and what stops it at 3am when it enters a loop. Everything
here is framework-agnostic. An agent of any kind (LangGraph, a hand-written tool loop or a Managed
Agents client) runs inside the same wrapper.

| Piece | Location |
|---|---|
| Safe runner, budgets, loops, checkpoints, ledger | `src/golden/agentops/` · `golden agent run\|report\|verify\|overnight` |
| Agent identities (team, owner, tools, budgets) | `src/golden/agentops/agents.yaml` (`GOLDEN_AGENTS_FILE`) |
| Token prices (data, not code) | `src/golden/agentops/pricing.yaml` (`GOLDEN_PRICING_FILE`) |
| LLM gateway (guard → budget → cache → route → retry/fallback → scan) | `golden.agentops.llm` · `golden llm ask` · `POST /api/v1/agentops/llm` |
| Guardrails + Envoy ext_authz | `golden.agentops.guardrails` · `security/llm/envoy-ext-authz.yaml` · `/ext_authz/*` |
| Red-team gate | `golden agent redteam` · `security/llm/redteam-workflow.yaml` (Argo + Garak) |
| Evals-as-monitoring, behavioural drift | `golden.agentops.evals` · `POST /api/v1/agentops/evals` |
| RAG with citations | `golden.ai.rag` · `golden rag ask` · `POST /api/v1/agentops/rag/ask` |
| Service | `agent-ops` :8099 |
| Alerts / dashboard | `observability/prometheus/rules/agentops_rules.yml` · Grafana *Agent Operations* |
| Runbook | [ops/runbooks/agent-ops/runaway-agent.md](../../ops/runbooks/agent-ops/runaway-agent.md) |

The model is **simulated by default**: deterministic, offline and free, so tests, demos and CI never
spend money. To use Claude, run `pip install '.[llm]'` and set `GOLDEN_LLM_PROVIDER=anthropic` with
`ANTHROPIC_API_KEY`. The client uses the official SDK, the default model is `claude-opus-5-5`, and the
server-side refusal fallback is enabled on Opus and Sonnet.

## 1. Your first production agent: the five failures

A tutorial agent fails in production in five predictable ways. Each one has a treatment in this platform:

| Failure | What it costs | Treatment |
|---|---|---|
| Runaway loop | four figures overnight | loop detection (stuck · bouncing · drifting) + step ceiling |
| Blown token budget | the CFO conversation | three budget gates, with breach behaviour (drain / stop / kill) decided in advance |
| No audit trail, no identity | can't say who ran what | registered identity per agent + hash-chained audit entry per run |
| Can't tell if it's working | silent quality decay | evals-as-monitoring + behavioural drift |
| No guardrails, leaks data | breach | input / tool / output guardrails at the gateway and the proxy |
| Fails mid-run, no checkpoint | pays twice | atomic per-step checkpoints, resume, drain on rollout |

`golden agent verify` proves each treatment. It runs every control with the mechanism turned off and
then on, and fails CI if any proof breaks.

## 2. The agent cost problem

**Why agent cost is different.** cost = requests × steps × tokens × retries. A loop multiplies the
last three. Input and output are priced separately and never averaged, because output tokens cost
about 5× input and looping agents re-send their whole context on every step.

**Making cost visible.** Every step is priced from the rate card and recorded as
`golden_agent_cost_usd_total{agent,team,model}`, along with tokens by direction, steps, runs by
result, and wasted spend. The run id is never a label, because it would have unbounded values.

**Budget caps and kill switches.** The three gates, in order:

1. **Pre-flight:** before the call, refuse if the estimated step cost would cross the per-run cap.
2. **Per-run:** after charging the actual cost.
3. **Per-day:** persisted to disk, so a restart can't reset it.

The platform kill switch beats all three. Breach behaviour is chosen per agent in `agents.yaml`:

- `drain` keeps the checkpoint, so the run can resume tomorrow.
- `stop` discards it.
- `kill` engages the platform kill switch file, so every agent and every autonomous action halts.

The money is always recorded, even when caps are disabled.

**Loops, retries and the cost of failure.** Loop detection catches a bouncing agent after 6 steps,
about $0.04. A cap-only run spends to the cap, about $0.14. An unguarded run on the same input projects
to roughly **$975 overnight** across 12 workers (`golden agent overnight`: the bill that never arrived).
In the gateway, retries use exponential backoff with jitter, go to a fallback model, and never retry a
non-retryable error.

**Cost per successful task.** `golden agent report` computes this as total spend divided by successful
runs, with failures kept in the numerator. That number survives a finance conversation. The report
also gives the failed-run tax (the share of spend on runs that failed), the money saved by checkpoints,
and spend by team and by agent for chargeback.

**Operating it.** The dashboard has four panels:
- What are we spending?
- What is it buying us?
- Who is spending it?
- How much is wasted?

The alerts fire on the *rate*, not the total. `AgentBurnRateFast` fires at 2× the monthly budget pace
within 5 minutes and pages. `AgentBurnRateSlow` fires at 1.2× over 2 hours and opens a ticket.
`AgentFailedRunTaxHigh` fires above 35%.

Two cost levers are built into the gateway:
- **Routing:** short prompts go to a small model.
- **Caching:** identical requests are served from cache at zero cost. Anthropic prompt-cache reads are
  priced at 0.1× input.

**Weekly review** (15 minutes, one named owner). Answer four questions:
1. What moved in spend?
2. Did cost per success rise?
3. Which loops fired?
4. Should any cap change?

## 3. Running agents in production

- **Identity:** an agent not registered in `agents.yaml` cannot run. Each identity names its team, its
  owner, its model, a **tool allowlist** (least privilege; an unlisted tool ends the run as `blocked`
  before any money is spent), its budgets and a written success definition.
- **Checkpointed runs:** completed steps are written atomically (tmp file, then rename), and resume
  skips them. On SIGTERM (Kubernetes rollout) the runner finishes the current step, checkpoints and
  exits `drained`. Size `terminationGracePeriodSeconds` to at least one step.
- **Run results:** `success · looped · capped · ceiling · drained · blocked · killed`. Each run appends
  one line to the ledger, writes one audit entry, and produces a trace (`trace_id` plus one span per
  step with tokens, cost and duration).
- **Per-integration health:** the gateway records `golden_llm_calls_total{model,status}` and latency per
  model, and the HTTP layer records per-route metrics for every service.

## 4. Observability for non-deterministic systems

Traditional monitoring assumes a correct answer exists. Agents break that assumption, so "working" is
defined three ways:

1. **Property checks as the SLI.** These are assertions every acceptable answer satisfies however it
   is worded: non-empty, within length, valid JSON with required fields, cites a source, grounded in
   the retrieved context, no secrets, no refusal when the question is answerable. The SLO is the share
   of sampled outputs that pass, for example 97%. It is alerted with the same multi-window burn rate
   as an availability SLO (`AgentEvalSLOFastBurn`).
2. **Behavioural baseline plus PSI.** Compare steps, cost and outcome mix against a known-good period.
   A PSI above 0.25 means the agent changed (new model, prompt edit, upstream data) before any user
   reports it.
3. **Golden set.** Fixed inputs are re-run on every prompt or model change as an offline gate, and on a
   schedule as an online canary.

What has no good answer yet, honestly: semantic correctness with no reference answer. Property checks
and grounding are proxies. Use human review on a sample, and LLM-as-judge only as a *ranked* signal,
never as ground truth.

## 5. Securing AI agents

Guardrails are enforced in code and at the proxy, not in the system prompt. A prompt-level rule can be
talked around. An ext_authz call cannot.

| OWASP LLM Top 10 (2025) | Control here |
|---|---|
| LLM01 Prompt Injection | input heuristics (instruction override, role tags, dev mode, jailbreak phrasing); RAG passages treated as data; pluggable classifier (Llama Guard / commercial AI firewall); Envoy ext_authz, fail-closed |
| LLM02 Sensitive Information Disclosure | secrets/PII in prompts blocked; output scanning redacts PII and withholds responses containing credentials; exfiltration patterns (URLs, markdown beacons) |
| LLM03 Supply Chain | pinned dependencies, SBOM + provenance on images, Trivy, pip-audit (existing pipeline) |
| LLM04 Data & Model Poisoning | model registry with gated, human-approved promotion; drift detection; JSON (not pickle) model artifacts; SHA-256 model manifest |
| LLM05 Improper Output Handling | output scan before anything leaves; structured outputs validated with property checks |
| LLM06 Excessive Agency | per-agent tool allowlist; ActionGovernor (allowlist, caps, autonomy modes, human approval, kill switch) |
| LLM07 System Prompt Leakage | extraction attempts blocked; output checked for system-prompt spans and distinctive codes |
| LLM08 Vector & Embedding Weaknesses | RAG answers only from retrieved passages, with citations; grounding eval on every answer |
| LLM09 Misinformation | "can't find it" instead of guessing; grounding score; eval SLO |
| LLM10 Unbounded Consumption | prompt size cap; per-caller daily tokens; per-run/per-day dollar caps; loop detection; rate limiting |

**Continuous red-teaming.** `golden agent redteam` runs the probe suite in CI and fails the build below
a 100% defended rate. The suite includes *indirect* probes, phrased innocently so they pass the input
filter; only output-side defences stop those. `security/llm/redteam-workflow.yaml` runs the same suite
plus Garak against the canary endpoint as an Argo Workflow. A failure blocks canary → stable.

To swap in a commercial AI firewall (Prisma AIRS, Lakera, Robust Intelligence), point the Envoy
`ext_authz` cluster at it, or pass its client as the gateway `classifier`. No application change is
needed.

## 6. Retrieval-augmented generation

The pipeline runs: chunk (500 characters with 100 overlap, on paragraph boundaries) → embed (feature
hashing, with no model download; or plug in sentence-transformers) → cosine top-k → numbered passages
→ an answer that must cite `[n]` and say "can't find that" otherwise. Grounding and citation evals run
on every answer.

```bash
golden rag ask "How long are PHI audit logs retained?" --docs docs/compliance
```
