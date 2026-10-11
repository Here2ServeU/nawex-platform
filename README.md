# Golden Platform

**A plug-and-play, end-to-end template for enterprise modernization on AWS, Azure, GCP and OpenShift.**

[![ci](https://github.com/Here2ServeU/nawex-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Here2ServeU/nawex-platform/actions/workflows/ci.yml)
[![containers](https://github.com/Here2ServeU/nawex-platform/actions/workflows/containers.yml/badge.svg)](https://github.com/Here2ServeU/nawex-platform/actions/workflows/containers.yml)
[![infra](https://github.com/Here2ServeU/nawex-platform/actions/workflows/infra.yml/badge.svg)](https://github.com/Here2ServeU/nawex-platform/actions/workflows/infra.yml)
[![security](https://github.com/Here2ServeU/nawex-platform/actions/workflows/security.yml/badge.svg)](https://github.com/Here2ServeU/nawex-platform/actions/workflows/security.yml)

Clone it, rename it, choose your cloud, and run one command. You get:

- **Landing zones** on AWS (EKS/ECR), Azure (AKS/ACR), GCP (GKE/Artifact Registry) or OpenShift. Each can add an optional GPU node pool. Deploys use keyless OIDC.
- **A VMware → OpenShift migration factory.** It takes an RVTools inventory and produces a readiness assessment and dependency-aware migration waves. It then generates Migration Toolkit for Virtualization (MTV) manifests for GitOps, with cutover and rollback runbooks.
- **Production-shaped services** for four domains: healthcare, financial services, GPU / AI-infrastructure optimization, and migration.
- **An AI engine** with LSTM/TCN forecasters, explainable risk scoring, and governed AIOps remediation (observe → analyze → plan → execute). GPU-accelerated training is built in.
- **AI security** built into every layer: guardrails and caps, autonomy modes, human approval, a kill switch, model integrity checks, auth and rate limiting, and a tamper-evident audit trail.
- **Day-2 operations:** Prometheus, Grafana, Loki, and Tempo, plus SLOs, alert rules, runbooks, chaos scripts, and a CI/CD pipeline with security scanning.

---

## Quick start (local, ~5 minutes)

```bash
git clone https://github.com/Here2ServeU/nawex-platform && cd nawex-platform
make bootstrap          # Python venv + Node deps + pre-commit
make check              # lint, typecheck, tests, app tests, infra validation (what CI runs)
make up                 # whole platform in Docker Compose
open http://localhost:8000/docs   # platform API (OpenAPI)
open http://localhost:3001        # executive console
make demo               # narrated demo + HTML reports for all four domains
```

## Adopt it for your engagement

```bash
make init SLUG=acme NAME="Acme Modernization"   # renames package, CLI, images, env vars, metrics
$EDITOR platform.yaml                           # cloud, region, environment, domains, AI-safety mode
make plan  CLOUD=aws ENV=dev                    # Terraform plan for the landing zone
make deploy CLOUD=aws ENV=dev                   # landing zone + registry + Helm install of the platform
```

`platform.yaml` is the only file you need to edit. Every `make` target reads its defaults from it, and you can override any value on the command line (`CLOUD=gcp ENV=prod`). In CI, run the **deploy** workflow with *cloud / environment / action*; it authenticates to AWS, Azure, or GCP with OIDC, so no cloud keys are stored in GitHub. Setup is covered in [docs/guides/deploy.md](docs/guides/deploy.md).

| Cloud | Cluster | Registry | Ingress / storage | Workload identity |
| --- | --- | --- | --- | --- |
| AWS | EKS | ECR | ALB · gp3 | IRSA |
| Azure | AKS | ACR | App Gateway / web app routing · managed-csi | Entra workload identity |
| GCP | GKE | Artifact Registry | GCE ingress · standard-rwo | GKE workload identity |
| OpenShift (incl. ROSA / ARO) | OCP | any | Routes · ODF | service accounts + SCC `restricted-v2` |

## VMware → OpenShift in four commands

```bash
golden migrate assess    --inventory ./rvtools-export/   # blockers & warnings per VM (RDM, shared disks, EOL OS, vGPU…)
golden migrate plan      --inventory ./rvtools-export/   # dependency-aware waves: pilot first, mission-critical last
golden migrate manifests --inventory ./rvtools-export/   # MTV NetworkMap/StorageMap/Plan/Migration per wave (+kustomization)
kubectl apply -k deploy/openshift/virtualization/operators  # OpenShift Virtualization + MTV operators
```

Waves are committed to `deploy/openshift/virtualization/waves/` and applied by Argo CD. The cutover itself is a governed action that needs a named human approver. The full runbook is in [docs/modernization/vmware-to-openshift.md](docs/modernization/vmware-to-openshift.md).

## AI security model

Every autonomous action passes through the **ActionGovernor**, and every model input and output passes **guardrails**.

| Control | Default | Configure |
| --- | --- | --- |
| Autonomy mode | `dry_run` (nothing executes) | `GOLDEN_AUTONOMY_MODE=dry_run\|supervised\|autonomous` |
| Human approval | critical actions (cutover, rollback, PHI isolation, settlement halt…) **always** require a named approver | `POST /v1/actions/{id}/approve` |
| Kill switch | off | `GOLDEN_KILL_SWITCH=true` or touch `GOLDEN_KILL_SWITCH_FILE` |
| Rate caps | 20 actions/hour, 5 per action, 5 targets max | `GOLDEN_MAX_ACTIONS_PER_HOUR` |
| Action allowlist | unknown actions denied | `golden.security.actions.ACTION_CATALOG` |
| Input guardrails | finite, bounded, size-capped inputs; OOD detection; scores clamped to [0, 1] | `golden.security.guardrails` |
| Model integrity | SHA-256 manifest + `torch.load(weights_only=True)` | `GOLDEN_MODEL_MANIFEST` |
| API protection | API keys, token-bucket rate limiting, body-size cap, security headers | `GOLDEN_API_KEYS`, `GOLDEN_RATE_LIMIT_PER_MINUTE` |
| Audit | hash-chained, PHI-redacted, verifiable (`GET /v1/audit`) | `GOLDEN_AUDIT_LOG` |

Details and the threat model are in [docs/security/ai-safety.md](docs/security/ai-safety.md).

## GPU

- **Training and inference:** CUDA → MPS → CPU auto-selection, bf16/fp16 mixed precision, TF32, pinned memory, and optional `torch.compile`. Run `make train`, and `golden gpu doctor` to see what's available.
- **GPU domain:** `gpu-optimizer` analyzes fleets from `nvidia-smi` or the DCGM exporter. It detects thermal throttling, ECC/XID faults, and idle or stranded GPUs, recommends consolidation and power caps, and estimates the dollar savings.

See [docs/guides/gpu-acceleration.md](docs/guides/gpu-acceleration.md) and [docs/verticals/gpu.md](docs/verticals/gpu.md).

## Repository layout

```text
platform.yaml            ← the one file you edit
Makefile                 ← every workflow, one verb each (`make help`)
compose.yaml             ← the whole platform locally
Dockerfile               ← one image for all Python services (`golden serve <service>`)
src/golden/
  ai/                    forecasting (LSTM/TCN), detection pipelines, explainability, ROI, AIOps agents, accel (GPU)
  security/              guardrails, action governor, kill switch, integrity, auth, rate limit, audit, redaction
  decision/              signal → incident → risk/severity → governed action
  gpu/                   GPU telemetry, fleet analysis, optimisation
  migration/             RVTools inventory, assessment, wave planning, MTV manifest generation
  services/              FastAPI microservices (fintech, healthcare, gpu, migration) on a shared foundation
  api/                   platform API (scoring, decisions, ROI, approvals, audit)
  robotics/              clinical-robotics safety interceptor + gRPC telemetry
apps/                    client-portal (executive console) · workload (instrumented target app)
deploy/
  terraform/             landing zones: live/{aws,azure,gcp}/{dev,staging,prod} + modules
  helm/golden/           platform chart + values-{aws,azure,gcp,openshift,local}.yaml
  openshift/             manifests, Helm values, virtualization (operators, MTV, waves)
  gitops/  k8s/          Argo CD / Flux, plain manifests
observability/           Prometheus rules (SLO, AI safety, GPU, migration), Grafana dashboards, Loki, Tempo
security/  ops/  docs/   policies (OPA, RBAC, Trivy) · runbooks, SRE, chaos · documentation
tests/                   pytest suite (unit, service contracts, models, robotics)
```

## Services

| Service | Port | Purpose |
| --- | --- | --- |
| `api` | 8000 | Platform API: scoring, decisions, ROI, approvals, audit, security status |
| `transaction-engine` · `fraud-detector` · `payment-gateway` | 8090–8092 | Financial services |
| `ehr-ingestion` · `clinical-decision` · `patient-gateway` | 8093–8095 | Healthcare (FHIR R4, NEWS2, HIPAA audit, consent) |
| `gpu-optimizer` | 8096 | GPU fleet optimization |
| `migration-planner` | 8097 | VMware → OpenShift assessment, waves, MTV manifests |
| `client-portal` · `workload` | 3001 · 8080 | Executive console · instrumented target app |

Every service exposes `/health`, `/ready`, and `/metrics` (Prometheus), and runs as non-root with a read-only filesystem.

## CI/CD

| Workflow | Runs on | What it does |
| --- | --- | --- |
| `ci` | push, PR | ruff, mypy, pytest (3.11/3.12, coverage ≥ 75%), CLI smoke, Node lint/test, shellcheck, compose/YAML validation, end-to-end rebrand test |
| `containers` | push, PR, tags | build, smoke-test, Trivy-scan, and push (main/tags) the three images to GHCR with SBOM + provenance |
| `infra` | infra changes | helm lint/template + kubeconform for every overlay; terraform fmt + validate for every module and environment |
| `security` | push, PR, weekly | gitleaks, Trivy (deps + IaC, SARIF), pip-audit, npm audit, CodeQL |
| `deploy` | manual | OIDC to AWS/Azure/GCP/OpenShift → Terraform plan/apply/destroy → Helm upgrade |

## Documentation

Start at [docs/README.md](docs/README.md): architecture, the modernization playbook, the VMware → OpenShift runbook, AI safety, GPU, the domain guides, operations runbooks, and compliance mappings (HIPAA, PCI-DSS, SOC 2).

---

*Golden Platform © 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
