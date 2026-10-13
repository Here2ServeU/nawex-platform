# Changelog

## [Unreleased]

### Added — platform gap closure
- **FinOps** (`golden.finops`, `golden finops`):
  - FOCUS-based showback and chargeback, with shared-cost allocation;
  - tag coverage, anomalies and month-end forecasts;
  - rightsizing and commitment recommendations, and Kubernetes cost allocation;
  - budget, anomaly and export Terraform modules for AWS, Azure and GCP;
  - an OPA tagging gate, OpenCost (Argo CD and Flux), an Infracost PR workflow, and FinOps alerts.
- **Enterprise networking** (`golden.network`, `golden network`):
  - AWS Transit Gateway hub with segmentation, inspection, hybrid DNS and Direct Connect;
  - PrivateLink endpoints restricted to the organization;
  - Azure hub-spoke and GCP Shared VPC modules, and the `live/aws/network` root;
  - an IP address planner, a reachability and segmentation checker, and `network.rego`.
- **Multi-cloud governance**:
  - Azure: management groups, Azure Policy, and Entra ID with PIM;
  - GCP: folders, org policy, deny policy and PAM;
  - AWS account vending;
  - Azure/GCP access models with a cross-cloud persona matrix (`golden iam multicloud|matrix`);
  - STRIDE threat models.
- **Platform engineering** (all opt-in): Argo Rollouts canary with analysis, KEDA and External Secrets in
  the chart; Karpenter and Velero in the EKS module; keyless cosign signing with SBOM attestation;
  Kyverno verifyImages; a ZAP DAST workflow.
- **Database performance** (`golden.database`, `golden db`): workload, EXPLAIN, index/vacuum and capacity
  advisors; an Aurora PostgreSQL module (Performance Insights, RDS Proxy, tuned parameters); PgBouncer and
  `postgres_exporter`; alerts, a dashboard and a runbook.
- **ML platform**:
  - a point-in-time feature store with a Feast equivalent;
  - Open Inference Protocol model server (`model-server` :8100) and KServe, vLLM and Triton manifests;
  - MIG, time-slicing and MPS planning (`golden gpu partition`), and GPU Operator config.
- **Modernization**: 7 Rs / TIME portfolio assessment, database migration assessment, an AWS DMS
  module, a strangler-fig facade on Kong, and a database cutover runbook.
- **New Relic via OpenTelemetry** (collector overlay plus an Argo CD app), a **CIS-style RHEL Ansible
  baseline**, and a **Jenkinsfile** mirroring CI.

### Fixed
- Agent operations, from the threat model:
  - RAG quarantines ingested chunks that carry injection payloads;
  - an agent with no tool allowlist now gets no tools (it previously got all of them);
  - the LLM response cache is scoped per caller.

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
