# Golden Platform Enterprise Runbook

## Purpose

This runbook defines operational procedures for running Golden Platform as an enterprise-grade reliability platform across regulated environments.

## Operating Model

- Tier 0: Platform control-plane and identity systems.
- Tier 1: Fintech and healthcare critical workloads.
- Tier 2: Analytics, batch jobs, and non-critical integrations.

## Startup and Validation

1. Bootstrap dependencies:

```bash
make bootstrap
```

2. Start the unified platform stack:

```bash
make up
```

3. Validate service health and telemetry:

```bash
scripts/tools/healthcheck.sh
```

## Incident Workflow

1. Detect via alerts in `observability/alerting`.
2. Triage severity and assign incident commander.
3. Stabilize with playbooks in `sre/recovery` and automation engine controls.
4. Recover service objectives and verify SLO restoration.
5. Publish post-incident review with corrective actions.

## Severity Definitions

- SEV-1: Customer-impacting outage of Tier 0 or Tier 1 workloads.
- SEV-2: Major degradation with active workarounds.
- SEV-3: Localized impact or non-critical reliability regression.

## SLO and Error Budget Operations

- Track SLI/SLO definitions under `sre/slis_slos`.
- Freeze risky changes when error budget burn exceeds policy thresholds.
- Require rollback readiness checks for high-risk deployments.

## Change Management

- Enforce canonical path policy with `make check`.
- Validate policy and security gates in CI.
- Use GitOps promotion from lower to higher environments with approval gates.

## Compliance and Audit Readiness

- Retain immutable logs and traces for regulated workflows.
- Store evidence artifacts under compliance documentation and controls.
- Run recurring control checks for IAM, secrets, and policy baselines.

## Recovery Objectives

- Tier 0/Tier 1 RTO: under 30 seconds where architecture supports active-active.
- Tier 0/Tier 1 RPO: near-zero for transactional and clinical critical paths.
- Validate recovery quarterly via controlled chaos and game-day exercises.
