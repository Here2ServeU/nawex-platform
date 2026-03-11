# DevSecOps Integration Guide

This guide maps DevSecOps responsibilities to concrete artifacts in the platform.

## 1) Infrastructure-as-Code (Terraform)
- **EKS baseline**: [terraform/modules/aws/eks](../../terraform/modules/aws/eks)
- **SecurityHub**: [terraform/modules/aws/securityhub](../../terraform/modules/aws/securityhub)
- **AWS Config**: [terraform/modules/aws/config](../../terraform/modules/aws/config)

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
- Playbook: [ops/playbooks/observability_dashboards.md](../../ops/playbooks/observability_dashboards.md)
- Core metrics: ingestion rate, Kafka lag, storage latency, error rate, saturation.

## 3) Kafka Operations
- Healthcheck playbook: [ops/playbooks/kafka_healthcheck.md](../../ops/playbooks/kafka_healthcheck.md)
- Local healthcheck tooling: [tools/kafka/README.md](../../tools/kafka/README.md)

## 4) CI/CD and Policy Gates
- Pipeline definition: [.github/workflows/ci.yml](../../.github/workflows/ci.yml)
- Policy gate script: [scripts/policy-gate.sh](../../scripts/policy-gate.sh)

## 5) Security and Compliance
- SecurityHub + Config enablement: [ops/playbooks/securityhub_config.md](../../ops/playbooks/securityhub_config.md)
- Evidence trail: Immutable log retention for decisions and changes.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
