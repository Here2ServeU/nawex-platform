# Concept map — course material → platform

Where each concept from the **Zero to AI Systems Engineer** course (`zero-2-ai-systems-engineer`), the
**Agent Cost Problem** reference repo (`agent-cost`) and the **Agent Operations Track** (five courses)
lives in this platform. "Existing" means it was already in the platform before this integration.

## Zero to AI Systems Engineer (18 chapters)

| Ch | Concept | Platform |
|---|---|---|
| 1–2 | Setup, synthetic data | existing: `golden.ai.datasets` simulators |
| 3 | Fraud classifier (stratified split, P/R/AUC), Isolation Forest | `golden.ai.lifecycle.fraud_model` (class-weighted logistic regression, calibrated threshold, JSON artifact); existing `ai/anomaly_detection` |
| 4 | MLflow tracking, registry, champion/staging aliases, promotion, rollback | `golden.ai.lifecycle.tracking` (MLflow mirror when `MLFLOW_TRACKING_URI` set), `registry` (gated, approver-required promotion, rollback) · `golden model promote\|rollback\|list` |
| 5–6 | Model API, Docker | existing: FastAPI services, non-root read-only image |
| 7–8 | Terraform, remote state, cloud modules | existing: `deploy/terraform` |
| 9 | CI/CD | existing `ci.yml` + new agent-ops / red-team / model-quality gates |
| 10 | Kubernetes | existing Helm chart (now with `agent-ops`) |
| 11 | Metrics, z-score anomaly detection | existing |
| 12 | AIOps engine, automated response, **trend (slope) rule** | existing loop + new slope/z-score `capacity_trend_risk` → `scale_up_replicas` |
| 13 | KS drift, gated retrain, scheduled workflow | `golden.ai.drift` (PSI + KS, no scipy), `golden.ai.lifecycle.retrain` · `.github/workflows/retrain.yml` · `golden model drift\|retrain` |
| 14 | Canary, feature flag, blue/green | `golden.ai.lifecycle.rollout.ModelRouter` (sticky canary 5→20→50→100 with analysis + auto-rollback, shadow, flag, blue/green) |
| 15 | Dashboards | existing + Grafana *Agent Operations* |
| 16 | LLM APIs | `golden.agentops.llm` (Claude via official SDK; simulated offline model) |
| 17 | RAG with citations | `golden.ai.rag` · `golden rag ask` |
| 18 | Production LLM: retries, cache, token budget, safety filter, metrics | `LLMGateway` |
| capstone | `/explain`, `/qa`, audit trail | RAG Q&A endpoint; existing fraud contributions + hash-chained audit |

Not carried over: the OpenAI and Gemini client variants. The provider interface (`LLMClient.complete`)
takes any client; the shipped real client is Claude.

## Agent Cost Problem (`agent-cost` repo + six modules + capstone)

| Concept | Platform |
|---|---|
| Prices as data, input ≠ output | `pricing.yaml`, `pricing.cost_usd` (+ cache read/write) |
| Spend as a Prometheus metric, attribution | `golden_agent_cost_usd_total{agent,team,model}` … |
| Three gates, decided breach behaviour | `budget.Budget` — pre-flight / per-run / per-day; drain / stop / **kill** all implemented (the reference repo only ever drained) |
| Loop detection (stuck / bouncing / drifting) | `loops.LoopDetector` — loop-caught steps are still charged to the day (fixes an undercount in the reference repo) |
| Checkpoint / resume | `checkpoint.CheckpointStore` + drain on SIGTERM |
| Ledger, cost per successful task, failed-run tax | `ledger.unit_economics` · `golden agent report` |
| Burn-rate alerts, failed-run-tax alert, 4-panel dashboard | `agentops_rules.yml`, `golden-agentops.json` |
| Routing and caching | `LLMGateway(small_model=…)`, response cache |
| Capstone: prove every step by turning it off | `golden agent verify` (CI) · `golden agent overnight` |

## Agent Operations Track

| Course | Platform |
|---|---|
| 1 Your First Production Agent | the five failures table in [README](./README.md) §1, each mapped to a control |
| 2 The Agent Cost Problem | §2 above |
| 3 Running AI Agents in Production | identity + tool allowlist, checkpoint + drain-on-rollout, ledger + audit + traces, per-integration metrics |
| 4 Observability for Non-Deterministic Systems | property-check SLI + burn-rate SLO, behavioural PSI, golden set; PSI drift + promotion gates |
| 5 Securing AI Agents | guardrails (OWASP LLM Top 10 mapping), Envoy ext_authz, output PII/secret scanning, red-team gate + Argo/Garak, audit |
