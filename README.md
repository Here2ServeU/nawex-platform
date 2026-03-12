# NERP Platform

NERP Platform is a multi-project repository for the Naweji Enterprise Reliability Platform. It brings together AI-driven resilience services, domain applications, platform APIs, infrastructure automation, observability, and vertical solutions for fintech and healthcare.

This root README is the entry point for the monorepo. Most implementation details, runbooks, and service-specific commands live in the README files inside each subproject.

## Repository Overview

The workspace is organized as a set of related projects rather than a single deployable application.

| Project | Purpose | Primary Doc |
|---|---|---|
| `nerp-core/` | Canonical platform structure, docs, scripts, tests, demos, and shared platform assets | [`nerp-core/README.md`](nerp-core/README.md) |
| `nerp-ai-engine/` | AIOps agents, anomaly detection, model orchestration, training, and remediation workflows | [`nerp-ai-engine/README.md`](nerp-ai-engine/README.md) |
| `nerp-api/` | API entry points, routes, and service integrations for platform access | `nerp-api/main.py` |
| `nerp-dashboard/` | App and frontend code for dashboards and user-facing visualizations | [`nerp-dashboard/app/README.md`](nerp-dashboard/app/README.md) |
| `nerp-decision-engine/` | Policy, rules, and decision logic services | `nerp-decision-engine/` |
| `nerp-automation/` | Workflow automation, scripts, cloud actions, and Kubernetes automation assets | `nerp-automation/` |
| `nerp-fintech/` | Fintech domain services such as fraud detection, transaction processing, and gateway simulation | [`nerp-fintech/README.md`](nerp-fintech/README.md) |
| `nerp-healthcare/` | Healthcare domain services for EHR ingestion, clinical decision support, and PHI-aware workflows | [`nerp-healthcare/README.md`](nerp-healthcare/README.md) |
| `nerp-infrastructure/` | Infrastructure, GitOps, Helm, Terraform, SRE, and security deployment assets | `nerp-infrastructure/` |
| `nerp-observability/` | Grafana, Prometheus, Loki, Tempo, alerting, and logging pipeline configuration | [`nerp-observability/README.md`](nerp-observability/README.md) |
| `nerp-ai-foundations-course/` | Education materials and course content related to the platform foundations | `nerp-ai-foundations-course/` |

## Platform Themes

- Reliability engineering for critical systems
- AI-assisted anomaly detection and remediation
- Regulated-domain support for fintech and healthcare
- Operational observability with metrics, logs, traces, and alerting
- Automation and infrastructure-as-code for repeatable delivery

## Suggested Starting Points

Choose the part of the platform you want to work on and start there.

### Platform Core

If you want the broadest architectural overview, start in `nerp-core/`.

```bash
cd nerp-core
make bootstrap
make platform-start
make health
```

See [`nerp-core/README.md`](nerp-core/README.md) for the canonical structure, demo flows, and testing guidance.

### AI Engine

If you are working on predictive models, orchestration, or remediation logic, start in `nerp-ai-engine/`.

```bash
cd nerp-ai-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

See [`nerp-ai-engine/README.md`](nerp-ai-engine/README.md) for the agent model, pipeline layout, and remediation flow.

### Observability Stack

If you need local monitoring and telemetry services, start in `nerp-observability/`.

```bash
cd nerp-observability
docker compose up -d
docker compose ps
```

See [`nerp-observability/README.md`](nerp-observability/README.md) for ports, architecture, and instrumentation details.

### Vertical Domain Services

- Fintech services: [`nerp-fintech/README.md`](nerp-fintech/README.md)
- Healthcare services: [`nerp-healthcare/README.md`](nerp-healthcare/README.md)

These modules contain domain-specific services, APIs, and compliance-oriented workflows.

## Working Model

There is no single root-level build or runtime entry point currently defined for the entire repository. In practice, work happens inside the relevant subproject:

- platform architecture and shared assets in `nerp-core/`
- model and agent development in `nerp-ai-engine/`
- service APIs in `nerp-api/`
- UI work in `nerp-dashboard/`
- domain services in `nerp-fintech/` and `nerp-healthcare/`
- infra and deployment assets in `nerp-infrastructure/`
- telemetry stack in `nerp-observability/`

## Repository Conventions

- Read the nearest subproject README before making changes.
- Keep changes scoped to the project you are modifying.
- Prefer documented scripts and Make targets where they exist.
- Use the root `.env.example` as a reference when configuring local environments.

## Documentation Map

- Core platform: [`nerp-core/README.md`](nerp-core/README.md)
- AI engine: [`nerp-ai-engine/README.md`](nerp-ai-engine/README.md)
- Observability: [`nerp-observability/README.md`](nerp-observability/README.md)
- Fintech: [`nerp-fintech/README.md`](nerp-fintech/README.md)
- Healthcare: [`nerp-healthcare/README.md`](nerp-healthcare/README.md)

If you want this root README to become a true operator guide, the next step would be to standardize a root-level bootstrap flow across the subprojects.