# Changelog

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
