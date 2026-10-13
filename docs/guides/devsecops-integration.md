# DevSecOps Integration Guide

This guide maps DevSecOps responsibilities to concrete artifacts in the platform.

## 1) Infrastructure-as-Code (Terraform)
- **EKS baseline**: [deploy/terraform/modules/aws/eks](../../deploy/terraform/modules/aws/eks)
- **SecurityHub**: [deploy/terraform/modules/aws/securityhub](../../deploy/terraform/modules/aws/securityhub)
- **AWS Config**: [deploy/terraform/modules/aws/config](../../deploy/terraform/modules/aws/config)

Example (dev environment):
```hcl
module "securityhub" {
  source = "../../../modules/aws/securityhub"
  enabled = true
  standards_arns = [
    "arn:aws:securityhub:::standards/aws-foundational-security-best-practices/v/1.0.0"
  ]
}

module "config" {
  source = "../../../modules/aws/config"
  name = "aiops-config-dev"
  bucket_name = "aiops-config-dev-logs"
  create_bucket = true
}
```

## 2) Observability and Dashboards
- Playbook: [ops/playbooks/observability_dashboards.md](../../ops/runbooks/playbooks/observability_dashboards.md)
- Core metrics: ingestion rate, Kafka lag, storage latency, error rate, saturation.

## 3) Kafka Operations
- Healthcheck playbook: [ops/playbooks/kafka_healthcheck.md](../../ops/runbooks/playbooks/kafka_healthcheck.md)
- Local healthcheck tooling: [tools/kafka/README.md](../../tools/kafka/README.md)

## 4) CI/CD and Policy Gates
- Pipeline definition: [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- Policy gate script: [make check](../.make check)

## 5) Security and Compliance
- SecurityHub + Config enablement: [ops/playbooks/securityhub_config.md](../../ops/runbooks/playbooks/securityhub_config.md)
- Evidence trail: Immutable log retention for decisions and changes.

## 6) Jenkins

GitHub Actions is the reference pipeline (`.github/workflows/`). For clients that standardise on
Jenkins, the root [`Jenkinsfile`](../../Jenkinsfile) runs the same `ci.yml` gates with the same
commands:
- Python 3.11 and 3.12: ruff, mypy, pytest (coverage gate 75%), CLI smoke test, and the agent-ops gates
  (`golden agent verify`, red-team, model retrain).
- Both Node apps: lint and test.
- ShellCheck, Compose validation, YAML/JSON parsing (`scripts/ci/check-yaml-json.py`), and the Ansible
  baseline's syntax check plus `ansible-lint`.

| GitHub Actions | Jenkins |
|---|---|
| `strategy.matrix` | declarative `matrix` (python, node) |
| `concurrency: cancel-in-progress` | `disableConcurrentBuilds(abortPrevious: true)` |
| `actions/setup-python`, `setup-node` | `agent { docker { image ... } }` per matrix cell |
| `upload-artifact` for junit/coverage | `junit` + `recordCoverage` (Coverage plugin, 75% line gate) |
| OIDC to the cloud (`deploy.yml`) | not mirrored; use the cloud's Jenkins OIDC plugin or a short-lived credential binding |

Requirements: an agent labelled `docker`, and the Pipeline, Docker Pipeline, JUnit, Coverage,
Workspace Cleanup and Timestamper plugins. The image build, signing, deploy and security-scan workflows
stay in GitHub Actions. When you port them, keep the same gates: Trivy, gitleaks, cosign sign and
verify, and the OPA plan gates (`scripts/iam-policy-gate.sh`). Change both pipelines in the same PR,
so that they don't drift apart.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
