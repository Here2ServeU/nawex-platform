# Structure Migration Guide

This repository now follows a canonical enterprise layout while preserving all original folders and runtime paths.

## Target Canonical Layout

```text
naweji-reliability-platform/
├── README.md
├── LICENSE
├── ROADMAP.md
├── CONTRIBUTING.md
├── docs/
│   ├── executive/
│   ├── architecture/
│   ├── compliance/
│   ├── product/
│   └── operations/
├── ai/
│   ├── datasets/
│   ├── feature_engineering/
│   ├── training/
│   ├── inference/
│   ├── evaluation/
│   └── models/
│       ├── lstm/
│       ├── tcn/
│       ├── anomaly_detection/
│       └── fraud_detection/
├── platform/
│   ├── telemetry/
│   ├── event_streams/
│   ├── resilience_engine/
│   ├── automation_engine/
│   └── notification_system/
├── healthcare/
│   ├── ehr_ingestion/
│   ├── clinical_monitoring/
│   └── compliance/
├── fintech/
│   ├── transaction_engine/
│   ├── fraud_detection/
│   └── payment_resilience/
├── infra/
│   ├── terraform/
│   ├── kubernetes/
│   ├── helm/
│   └── networking/
├── gitops/
│   ├── argocd/
│   └── environments/
├── observability/
│   ├── prometheus/
│   ├── grafana/
│   └── alerting/
├── security/
│   ├── iam/
│   ├── secrets/
│   └── policies/
├── sre/
│   ├── slis_slos/
│   ├── chaos_testing/
│   └── recovery/
├── scripts/
│   ├── bootstrap.sh
│   ├── start_platform.sh
│   ├── start_ai.sh
│   └── demo.sh
└── tests/
    ├── unit/
    ├── integration/
    └── performance/
```

## Non-Destructive Policy

- Keep all original folders and files in place.
- Add canonical folders for enterprise consistency and clearer onboarding.
- Use wrapper scripts and mapping docs to avoid breaking existing workflows.

## Legacy to Canonical Mapping

- `docs/01-executive/` and existing docs assets remain valid, with canonical entry at `docs/executive/`.
- `ai/features/` remains available; canonical ML path is `ai/feature_engineering/`.
- `platform/resilience-engine/` and `platform/notification-engine/` remain available; canonical names are `platform/resilience_engine/` and `platform/notification_system/`.
- `fintech/transaction-engine/` and `fintech/fraud-detection/` remain available; canonical names are `fintech/transaction_engine/` and `fintech/fraud_detection/`.
- `healthcare/ehr-ingestion/` and `healthcare/clinical-decision-support/` remain available; canonical names are `healthcare/ehr_ingestion/` and `healthcare/clinical_monitoring/`.
- `sre/slis-slos/` and `sre/chaos/` remain available; canonical names are `sre/slis_slos/` and `sre/chaos_testing/`.
- Top-level `terraform/`, `k8s/`, and `helm/` remain available while `infra/terraform/`, `infra/kubernetes/`, and `infra/helm/` are the canonical infrastructure roots.

## Enterprise Architecture Intent

NERP is organized as an AI-driven reliability platform for critical infrastructure with:

- Predictive intelligence: LSTM/TCN and anomaly model domains in `ai/models/`.
- Enterprise resilience: failover, event-stream, and automation capabilities under `platform/`.
- Regulated verticals: explicit `healthcare/` and `fintech/` bounded contexts.
- Multi-cloud readiness: infra, GitOps, and observability layers separated for AWS/Azure/GCP/OCI deployment patterns.

## Next Migration Phases

1. Move active workloads into canonical underscore paths where safe.
2. Update CI pipelines and docs references to canonical-first paths.
3. Keep compatibility aliases until validation passes across all environments.
4. Archive legacy duplicates after enterprise regression testing completes.
