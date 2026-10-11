# Troubleshooting Guide (All Domains)

## 1) Application (Express App)
**Symptoms**: App won’t start, 5xx responses, /metrics empty
- Ensure dependencies are installed: `npm --prefix app install`
- Check port 8080 is free
- Verify `/metrics` is reachable: `scripts/tools/healthcheck.sh`

## 2) AIOps Orchestrator
**Symptoms**: Import errors, no cycles, config not loaded
- Verify `ai/.venv` exists and dependencies installed
- Ensure `src/golden/ai/__init__.py` exists (package imports)
- Check `src/golden/ai/agents/agent_config.yaml` for `source: http` and endpoint

## 3) Data Pipelines (src/golden/ai/pipelines)
**Symptoms**: Model training failures, missing data
- Confirm required Python libs are installed
- Run pipeline scripts from repo root to preserve paths

## 4) Remediation Engine
**Symptoms**: No actions executed, rules ignored
- Validate YAML syntax in `src/golden/ai/remediation/remediation_rules.yaml`
- Confirm `executor.mode` is `active` if you want live actions

## 5) Observability
**Symptoms**: Metrics missing, noisy signals
- Validate `/metrics` output
- Reduce chaos injection or reset state via `/ops/heal`

## 6) GitOps (ArgoCD/Flux)
**Symptoms**: Manifests not syncing
- Verify cluster context in kubeconfig
- Validate YAML schemas in `gitops/`

## 7) Helm Charts
**Symptoms**: Chart install fails
- Run `helm lint` on the relevant chart
- Check `values.yaml` required fields

## 8) Kubernetes Manifests
**Symptoms**: Pods crashloop, service unreachable
- Validate namespace and service selectors
- Check `k8s/` manifests for port alignment

## 9) Terraform
**Symptoms**: Plan/apply failures
- Verify provider credentials and region settings
- Run `terraform fmt` and `terraform validate`

## 10) Robotics Demo (docker-compose)
**Symptoms**: Containers fail to build/start
- Ensure Docker is running
- Check for file path issues in `src/golden/robotics/grpc/Dockerfile`

## 11) Scripts & Tooling
**Symptoms**: `jq` missing, scripts fail
- Install `jq` or remove `| jq .` in scripts
- Ensure scripts are executable: `chmod +x scripts/*.sh`

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
