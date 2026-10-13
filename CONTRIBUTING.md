# Contributing

## Setup
```bash
make bootstrap      # .venv + Python (dev, ml, robotics) + Node deps + pre-commit hooks
make check          # exactly what CI runs: lint, typecheck, tests, app tests, infra validation
```

## Workflow
1. Branch from `main`; keep pull requests small and focused.
2. Add or update tests with every behaviour change — the coverage gate is 75%.
3. `make check` must pass locally before you open a PR.
4. Changes to `src/golden/security/` (guardrails, caps, kill switch, approvals, audit) need a second reviewer.

## Conventions
- Python: ruff (lint + format), mypy, pytest. Services are FastAPI apps built with
  `golden.services.common.create_app` so health, metrics, auth, rate limiting and security headers are uniform.
- Any new autonomous action must be added to `ACTION_CATALOG` (with a risk tier) **and** `HANDLERS`;
  a test enforces both.
- Infrastructure: `terraform fmt`, `helm lint`, kubeconform (`make validate-infra`).
- Shell: `set -euo pipefail`, shellcheck-clean, bash 3.2 compatible (macOS).
- Never commit secrets, kubeconfigs, Terraform state or model weights (see `.gitignore`).

## Pull requests
Describe user-facing impact, risk, and rollback. Update docs when behaviour or architecture changes.
