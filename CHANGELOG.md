# Changelog

## [Unreleased]

### Added
- **AWS identity governance domain** (`identity`):
  - persona-based access model (`security/identity/access-model.yaml`) mapping AD groups (SCIM via
    PingFederate) to IAM Identity Center permission sets per account group;
  - Terraform modules `aws/org-guardrails` (SCPs: root/IAM-user denial, mandatory permission boundary,
    security-service protection, region allow-list; RCP: data perimeter), `aws/identity-center`,
    `aws/permission-boundary` and `aws/wiz-connector`, plus the `live/aws/org` root;
  - OPA plan gate `security/policies/opa/aws-iam.rego` with tests and `scripts/iam-policy-gate.sh`;
  - `golden iam model|roles|gaps|controls`, the `identity-governance` service (:8098), Prometheus
    alerts, and the governed `quarantine_iam_role` / `delete_iam_role` actions.

- **AI agent operations** (`golden.agentops`, service `agent-ops` :8099, `golden agent|llm|rag`):
  - a safe runner with agent identity and tool allowlists;
  - three-gate dollar budgets, with drain, stop and kill all implemented;
  - loop detection, checkpointing and drain-on-rollout;
  - a run ledger with unit economics, and proofs that every control works (`golden agent verify`, run in CI);
  - an LLM gateway (Claude via the official SDK, or a simulated offline model) that handles guardrails,
    per-caller token budgets, caching, routing, retries and fallback, plus system-prompt leak detection;
  - OWASP LLM Top 10 guardrails, an Envoy ext_authz endpoint, a red-team gate (and an Argo/Garak workflow),
    and evals-as-monitoring with behavioural PSI drift;
  - Prometheus rules and a Grafana dashboard.
- **RAG** (`golden.ai.rag`): chunking, hashing embeddings, a vector index, and grounded answers with citations.
- **ML lifecycle** (`golden.ai.lifecycle`, `golden model …`):
  - experiment tracking with an optional MLflow mirror;
  - a trained JSON-serialised fraud model;
  - a model registry with gated, approver-required promotion and rollback;
  - PSI/KS drift (`golden.ai.drift`) with gated retraining, plus a weekly `retrain.yml` workflow;
  - canary, shadow, feature-flag and blue/green routing.
- AIOps analyzer: a slope and z-score capacity-trend rule that catches slow climbs before a threshold is crossed.

### Changed
- The EKS module and the `live/aws/{dev,staging,prod}` landing zones attach the `golden-workload-boundary`
  permission boundary to every IAM role they create.

## [2.0.0] — 2026-10-11
Complete rewrite as the **Golden Platform**: a plug-and-play, end-to-end enterprise modernization template.

### Added
- Single installable Python package `golden` with a `golden` CLI and one container image for all services.
- Four business domains: healthcare, fintech, **GPU / AI-infrastructure optimisation** and
  **VMware → OpenShift Virtualization migration** (RVTools assessment, wave planning, MTV manifests).
- **AI-safety layer**: input guardrails and output caps, OOD detection, action governor (allowlist,
  blast-radius and rate caps, autonomy modes, mandatory human approval for critical actions, kill switch),
  SHA-256 model manifests with `weights_only` loading, API-key auth, rate limiting, hash-chained audit log,
  PHI/PII redaction.
- **GPU acceleration**: CUDA → MPS → CPU selection, AMP (bf16/fp16), TF32, pinned memory, optional `torch.compile`.
- `platform.yaml` single config, `scripts/init-project.sh` rebrand, Makefile lifecycle, multi-cloud
  (AWS/Azure/GCP/OpenShift) landing zones and keyless OIDC deploy workflow.
- Test suite (pytest, node:test), ruff, mypy, actionlint-clean CI with security scanning.

### Changed
- All services rebuilt on FastAPI with uniform `/health`, `/ready`, `/metrics` (Prometheus).
- Repository restructured: `src/`, `apps/`, `deploy/`, `observability/`, `security/`, `ops/`, `docs/`.

### Removed
- NAWEX product branding from code and domains (author byline retained).
- Committed virtualenv, placeholder model pickles, and the 7-day AI course.
