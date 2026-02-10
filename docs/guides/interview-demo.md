# Interview Demo Runbook

Use this runbook to showcase production-style reliability engineering in 10–15 minutes.

## Demo Flow (10–15 minutes)
1. **Show Architecture**: Highlight the multi-domain structure (AI, app, GitOps, Terraform, SRE).
2. **Start Services**: App + Orchestrator, then robotics demo (optional).
3. **Show Observability**: Live metrics and `/metrics` payload.
4. **Inject Chaos**: Latency, error spike, CPU, memory leak.
5. **Explain AIOps Loop**: Observe → Analyze → Plan → Execute.
6. **Show Remediation**: Reset with `/ops/heal` and demonstrate recovery.

## Tools to Showcase
- **Observability**: Prometheus metrics endpoint, log-driven AIOps.
- **Chaos Engineering**: Built-in chaos endpoints + traffic generator.
- **Security & Compliance**: SOC2/HIPAA docs in `docs/compliance/`.
- **GitOps**: ArgoCD/Flux manifests in `gitops/`.
- **Infrastructure-as-Code**: Terraform modules in `terraform/`.
- **Kubernetes Packaging**: Helm charts in `helm/`.
- **Load Testing**: k6 script in `tools/k6/`.
- **API Exercises**: VS Code REST client file in `tools/http/`.
- **Supply Chain Security**: Trivy script in `scripts/`.

## Suggested Talking Points
- “The app is designed to emit golden signals out-of-the-box.”
- “Chaos endpoints make reliability measurable, not theoretical.”
- “The AI loop automates detection and remediation safely in dry-run by default.”
- “Everything is documented and reproducible—GitOps + IaC + runbooks.”

## Fast Commands
```bash
scripts/healthcheck.sh
scripts/chaos_demo.sh
scripts/heal.sh
```
