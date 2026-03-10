# Naweji Enterprise Reliability Platform (NERP)

AI-driven reliability platform for critical infrastructure in fintech and healthcare.
Designed for enterprise scale, predictive intelligence, and multi-cloud resilience.

## Executive Summary

NERP combines AI/ML, observability, resilience automation, and regulated-domain controls to reduce downtime risk for mission-critical systems.

- Reliability target: five-nines operating model (99.999%)
- Fintech target: sub-50ms fraud scoring paths
- Healthcare target: low-latency clinical signal processing with PHI-aware controls
- Resilience target: rapid failover and controlled recovery workflows

## Why This Platform Wins

### Business Value

- Prevents revenue-impacting outages in payment and clinical workflows.
- Improves incident economics through predictive detection and faster recovery.
- Supports audit readiness with policy, traceability, and operational evidence paths.

### Engineering Value

- Clear domain boundaries and enterprise repository structure.
- Canonical migration model with backward-compatible legacy paths.
- Makefile-first operations for faster local demos and repeatable workflows.

## Core Platform Capabilities

- Fintech reliability services in [fintech/](fintech/)
- Healthcare reliability services in [healthcare/](healthcare/)
- AI model lifecycle and inference in [ai/](ai/)
- Platform automation and resilience controls in [platform/](platform/)
- Enterprise infrastructure and cloud deployment in [infra/](infra/)
- Policy-driven delivery and promotion in [gitops/](gitops/)
- Full-stack observability in [observability/](observability/)
- Security controls and governance in [security/](security/)
- SRE playbooks and reliability practices in [sre/](sre/)

## Architecture Snapshot

```text
Tenants -> API Layer -> Domain Engines -> AI Inference -> Event Backbone -> Observability -> Governance
```

- Domain engines: [fintech/](fintech/), [healthcare/](healthcare/)
- AI domains: [ai/models/lstm](ai/models/lstm), [ai/models/tcn](ai/models/tcn), [ai/models/anomaly_detection](ai/models/anomaly_detection), [ai/models/fraud_detection](ai/models/fraud_detection)
- Resilience domains: [platform/event_streams](platform/event_streams), [platform/resilience_engine](platform/resilience_engine), [platform/automation_engine](platform/automation_engine), [platform/notification_system](platform/notification_system)

## Canonical NERP Structure (2026)

NERP now includes a canonical layout designed to support:

1. SaaS platform operations
2. PhD research workflows
3. Engineering portfolio quality
4. Training and education tracks
5. Investor-ready architecture narratives

Primary canonical paths:

- `platform/`
- `ai/`
- `decision_engine/`
- `automation/`
- `data_platform/`
- `api/`
- `frontend/`
- `infrastructure/`
- `security/`
- `compliance/`
- `datasets/`
- `models/`
- `experiments/`
- `demos/`
- `verticals/`
- `research/`
- `education/`

Reference docs:

- [docs/architecture/nerp-platform-overview.md](docs/architecture/nerp-platform-overview.md)
- [docs/architecture/canonical-path-index.md](docs/architecture/canonical-path-index.md)
- [STRUCTURE_MIGRATION.md](STRUCTURE_MIGRATION.md)

## Project Folders

### Top-Level Repository Folders

- [ai/](ai/)
- [app/](app/)
- [assets/](assets/)
- [docs/](docs/)
- [fintech/](fintech/)
- [gitops/](gitops/)
- [healthcare/](healthcare/)
- [helm/](helm/)
- [infra/](infra/)
- [integrations/](integrations/)
- [k8s/](k8s/)
- [observability/](observability/)
- [openshift/](openshift/)
- [ops/](ops/)
- [platform/](platform/)
- [robotics/](robotics/)
- [scripts/](scripts/)
- [security/](security/)
- [sre/](sre/)
- [terraform/](terraform/)
- [tests/](tests/)
- [tools/](tools/)

### Canonical Domain Structure

- Docs: [docs/executive/](docs/executive/), [docs/architecture/](docs/architecture/), [docs/compliance/](docs/compliance/), [docs/product/](docs/product/), [docs/operations/](docs/operations/)
- AI: [ai/feature_engineering/](ai/feature_engineering/), [ai/training/](ai/training/), [ai/inference/](ai/inference/), [ai/evaluation/](ai/evaluation/), [ai/models/](ai/models/)
- Platform: [platform/telemetry/](platform/telemetry/), [platform/event_streams/](platform/event_streams/), [platform/resilience_engine/](platform/resilience_engine/), [platform/automation_engine/](platform/automation_engine/), [platform/notification_system/](platform/notification_system/)

Migration details: [STRUCTURE_MIGRATION.md](STRUCTURE_MIGRATION.md)

## OpenShift Integration

OpenShift deployment is fully integrated and production-oriented.

- Guides:
  - [openshift/README.md](openshift/README.md)
  - [openshift/QUICKSTART.md](openshift/QUICKSTART.md)
  - [openshift/TROUBLESHOOTING.md](openshift/TROUBLESHOOTING.md)
  - [openshift/OPERATIONS.md](openshift/OPERATIONS.md)
- Deployment scripts:
  - [scripts/deploy-openshift.sh](scripts/deploy-openshift.sh)
  - [scripts/deploy-openshift-helm.sh](scripts/deploy-openshift-helm.sh)
- Manifests and values:
  - [openshift/manifests/](openshift/manifests/)
  - [openshift/helm-values/](openshift/helm-values/)

Quick deploy:

```bash
oc login --token=<token> --server=https://<api-server>:6443
scripts/deploy-openshift.sh
oc get pods -A -w
```

## Getting Started

### Local Bootstrap

```bash
make bootstrap
make platform-start
make health
```

Cleanup local demo resources:

```bash
make cleanup
```

### Demo Flows (Separated by Domain)

Healthcare demo:

```bash
make demo-healthcare
```

- Starts healthcare services via [scripts/start_healthcare.sh](scripts/start_healthcare.sh)
- Generates EHR traffic via [scripts/generate-ehr-events.sh](scripts/generate-ehr-events.sh)

Fintech demo:

```bash
make demo-fintech
```

- Starts fintech services via [scripts/start_fintech.sh](scripts/start_fintech.sh)
- Generates transaction traffic via [scripts/generate-transactions.sh](scripts/generate-transactions.sh)

## Testing and Quality

- Unit tests: [tests/unit/](tests/unit/)
- Integration tests: [tests/integration/](tests/integration/)
- End-to-end scenarios: [tests/e2e/](tests/e2e/)
- Performance tests: [tests/performance/](tests/performance/)
- Security tests: [tests/security/](tests/security/)

Test execution guide: [tests/README.md](tests/README.md)

## Security and Compliance

- Security controls: [security/](security/)
- Compliance docs: [docs/compliance/](docs/compliance/)
- Observability evidence: [observability/](observability/)
- Reliability operations: [sre/](sre/)

## Strategic Documents

- [docs/executive/100M_PLATFORM_BLUEPRINT.md](docs/executive/100M_PLATFORM_BLUEPRINT.md)
- [docs/product/PLATFORM_CAPABILITIES.md](docs/product/PLATFORM_CAPABILITIES.md)
- [docs/operations/ENTERPRISE_RUNBOOK.md](docs/operations/ENTERPRISE_RUNBOOK.md)
- [NERP_PLATFORM_OVERVIEW.md](NERP_PLATFORM_OVERVIEW.md)

## License

Licensed under [LICENSE](LICENSE).
