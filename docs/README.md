# Golden Platform Documentation

Docs-as-code for the Golden Platform golden-path monorepo. Start with the
[architecture overview](./architecture/overview.md) and the [quickstart](./guides/quickstart.md).

## Start here

| Doc | What it covers |
|---|---|
| [architecture/overview.md](./architecture/overview.md) | Golden layout, CLI, services & ports, runtime diagram, the four business domains |
| [guides/quickstart.md](./guides/quickstart.md) | Install, `golden` CLI demos, `docker compose`, APIs, chaos |
| [security/ai-safety.md](./security/ai-safety.md) | AI threat model and controls: guardrails, action budgets, approvals, kill switch, integrity, auth, audit, redaction |
| [modernization/README.md](./modernization/README.md) | End-to-end modernization playbook and how to use this repo as an engagement template |
| [CLAIMS.md](./CLAIMS.md) | Claims register: every number in the docs, with its evidence command or its label as a target |

## Business domains

| Domain | Docs |
|---|---|
| Healthcare | [verticals/healthcare.md](./verticals/healthcare.md) · [product/healthcare.md](./product/healthcare.md) · [04-product/healthcare-edition.md](./04-product/healthcare-edition.md) |
| Fintech | [verticals/fintech.md](./verticals/fintech.md) · [product/fintech.md](./product/fintech.md) · [04-product/fintech-edition.md](./04-product/fintech-edition.md) |
| GPU / AI infrastructure | [verticals/gpu.md](./verticals/gpu.md) · [04-product/ai-infra-edition.md](./04-product/ai-infra-edition.md) · [guides/gpu-acceleration.md](./guides/gpu-acceleration.md) |
| Modernization / migration | [modernization/README.md](./modernization/README.md) · [modernization/vmware-to-openshift.md](./modernization/vmware-to-openshift.md) · runbooks: [cutover](../ops/runbooks/migration/cutover.md), [rollback](../ops/runbooks/migration/rollback.md) |
| AI agent operations | [agent-operations/README.md](./agent-operations/README.md) · [concept map](./agent-operations/concept-map.md) · runbook: [runaway agent](../ops/runbooks/agent-ops/runaway-agent.md) |
| AWS identity governance | [modernization/aws-iam-modernization.md](./modernization/aws-iam-modernization.md) · runbook: [guardrail rollout & break-glass](../ops/runbooks/identity/guardrail-rollout.md) |

## Architecture

- [overview.md](./architecture/overview.md) — golden-path layout (start here)
- [platform-overview.md](./architecture/platform-overview.md) — narrative platform overview
- [01-high-level-architecture.md](./architecture/01-high-level-architecture.md)
- [02-data-flow-diagrams.md](./architecture/02-data-flow-diagrams.md)
- [03-infrastructure-topology.md](./architecture/03-infrastructure-topology.md)
- [04-predictive-reliability-framework.md](./architecture/04-predictive-reliability-framework.md)
- [05-active-active-resilience.md](./architecture/05-active-active-resilience.md) — design target (not implemented)
- [06-quantum-optimization-layer.md](./architecture/06-quantum-optimization-layer.md) — research note, not implemented
- [ai-architecture.md](./architecture/ai-architecture.md) · [decision-engine.md](./architecture/decision-engine.md) · [automation-layer.md](./architecture/automation-layer.md) · [data-pipeline.md](./architecture/data-pipeline.md)
- [api-specifications.md](./architecture/api-specifications.md) — REST (OpenAPI) / gRPC strategy
- [multi-tenancy.md](./architecture/multi-tenancy.md) · [zero-trust.md](./architecture/zero-trust.md)
- [advanced-observability.md](./architecture/advanced-observability.md)
- [canonical-path-index.md](./architecture/canonical-path-index.md) · [structure-migration-legacy.md](./architecture/structure-migration-legacy.md) — historical layout notes
- [diagrams/splunk-architecture.mmd](./diagrams/splunk-architecture.mmd) · [assets/images](./assets/images/README.md)

## AI engine, research & robotics

- [ai-engine/README.md](./ai-engine/README.md) — agents, models (LSTM/TCN), pipelines (`golden.ai`)
- [research/README.md](./research/README.md) — methodologies: [LSTM SLI](./research/methodology/lstm_sli_methodology.md), [fraud](./research/methodology/fraud_detection_methodology.md), [PHI anomaly](./research/methodology/phi_anomaly_methodology.md), [clinical safety](./research/methodology/clinical_safety_methodology.md)
- [robotics/README.md](./robotics/README.md) · [robotics/overview.md](./robotics/overview.md)

## Security & compliance

- [security/ai-safety.md](./security/ai-safety.md)
- [modernization/aws-iam-modernization.md](./modernization/aws-iam-modernization.md) — IAM Identity Center, SCPs/RCPs, permission boundaries, OPA, Wiz
- Compliance docs are control mappings, not certifications.
- Healthcare: [HIPAA mapping](./compliance/01-hipaa-compliance-mapping.md) · [HDS privacy](./compliance/02-data-privacy-hds.md) · [hipaa.md](./compliance/hipaa.md)
- Financial: [PCI DSS mapping](./compliance/06-pci-dss-compliance-mapping.md) · [SOX](./compliance/07-sox-compliance-mapping.md) · [PSD2](./compliance/08-psd2-open-banking.md) · [GLBA](./compliance/09-glba-financial-privacy.md) · [pci-dss.md](./compliance/pci-dss.md)
- Cross-cutting: [audit logging](./compliance/03-audit-logging-policy.md) · [DR plan](./compliance/04-disaster-recovery-plan.md) · [PQC readiness plan](./compliance/05-quantum-safe-encryption.md) · [SOC 2](./compliance/soc2.md)

## Guides

- [quickstart.md](./guides/quickstart.md) · [running-locally.md](./guides/running-locally.md) · [developer-setup.md](./guides/developer-setup.md) · [developer-onboarding.md](./guides/developer-onboarding.md)
- [gpu-acceleration.md](./guides/gpu-acceleration.md)
- [platform-integration.md](./guides/platform-integration.md) · [platform-smoke-test.md](./guides/platform-smoke-test.md) · [enterprise-testing.md](./guides/enterprise-testing.md)
- [devsecops-integration.md](./guides/devsecops-integration.md) · [splunk-observability.md](./guides/splunk-observability.md)
- [troubleshooting.md](./guides/troubleshooting.md) · [interview-demo.md](./guides/interview-demo.md)

## Operations

- [operations/ENTERPRISE_RUNBOOK.md](./operations/ENTERPRISE_RUNBOOK.md)
- [05-operations/sre-slos.md](./05-operations/sre-slos.md) · [05-operations/quickstart.md](./05-operations/quickstart.md)
- Runbooks and SRE material live outside `docs/`: [ops/runbooks](../ops/runbooks/README.md), [ops/sre](../ops/sre/README.md)
- Observability stack, metric contract and alert routing: [observability/README.md](../observability/README.md)

## Product & business

- Editions: [editions.md](./04-product/editions.md) · [feature-matrix.md](./04-product/feature-matrix.md) · [release-plan.md](./04-product/release-plan.md)
- [product/PLATFORM_CAPABILITIES.md](./product/PLATFORM_CAPABILITIES.md) · [product/core-platform.md](./product/core-platform.md)
- Executive: [vision](./01-executive/vision.md) · [problem statement](./01-executive/problem-statement.md) · [product overview](./01-executive/product-overview.md) · [target market](./01-executive/target-market.md) · [pricing model](./01-executive/pricing-model.md) · [investor summary](./01-executive/investor-summary.md) · [platform blueprint](./executive/100M_PLATFORM_BLUEPRINT.md)
- Demos: [demo script](./06-demos/demo-script.md) · [fintech](./06-demos/fintech-demo.md) · [healthcare](./06-demos/healthcare-demo.md) · [investor](./06-demos/investor-demo.md)
- [consulting/consulting_playbook.md](./consulting/consulting_playbook.md) · [guides/EXECUTIVE-PORTFOLIO.md](./guides/EXECUTIVE-PORTFOLIO.md) · [book-guide.md](./book-guide.md)

## Documentation standards

1. **Context over config** — explain the *why*, not just the *what*.
2. **Living artifacts** — every PR that changes behaviour, ports, metrics or commands updates these docs.
3. **Paths are repo-root relative** (`src/golden/...`, `deploy/...`, `ops/...`) and commands use the `golden` CLI.
4. **Incident readiness** — written for the 3 AM on-call engineer.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
