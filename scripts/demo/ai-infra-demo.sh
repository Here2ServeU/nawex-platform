#!/usr/bin/env bash
# ai-infra-demo.sh: segment runner for the 30-minute AI infrastructure demo.
# Script and talk track: docs/guides/ai-infra-demo-30min.md
#
#   scripts/demo/ai-infra-demo.sh preflight   # tools, logins, sibling repos (run the day before)
#   scripts/demo/ai-infra-demo.sh prep        # pre-run the three terraform plans (slow; before recording)
#   scripts/demo/ai-infra-demo.sh clouds      # 1. GPU landing zones on EKS, AKS, GKE
#   scripts/demo/ai-infra-demo.sh gpu         # 2. GPU Operator, DCGM, MIG, time-slicing
#   scripts/demo/ai-infra-demo.sh serving     # 3. LLM/model serving, autoscaling, canaries
#   scripts/demo/ai-infra-demo.sh mlops       # 4. Drift -> retrain -> gated promotion
#   scripts/demo/ai-infra-demo.sh sre         # 5. SLOs, OTel, GitOps fleet, chaos
#   scripts/demo/ai-infra-demo.sh all         # every segment in order
#
# Environment:
#   WORKSPACE=..        folder holding the sibling repos (see preflight)
#   CLOUDS="aws azure gcp"
#   GCP_PROJECT=...     needed for the GKE plan
#   LIVE=1              also run kubectl checks against the current kube context
#                       (only when a real cluster with a GPU node is up)
#   PAUSE=0             do not stop between steps (default: wait for Enter)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORKSPACE="${WORKSPACE:-$(cd "$ROOT/.." && pwd)}"
CLOUDS="${CLOUDS:-aws azure gcp}"
LIVE="${LIVE:-0}"
PAUSE="${PAUSE:-1}"
OUT="$ROOT/demo_output/ai-infra"
GOLDEN="${GOLDEN:-$ROOT/.venv/bin/golden}"
export GOLDEN_AGENTOPS_DIR="${GOLDEN_AGENTOPS_DIR:-$OUT/agentops}"
mkdir -p "$OUT"
cd "$ROOT"

B=$'\033[1m'; C=$'\033[36m'; Y=$'\033[33m'; G=$'\033[32m'; R=$'\033[31m'; N=$'\033[0m'

title() { printf '\n%s══════ %s ══════%s\n' "$B$C" "$*" "$N"; }
say()   { printf '%s▸ %s%s\n' "$Y" "$*" "$N"; }
pause() { [[ "$PAUSE" == "1" ]] && { printf '%s  [Enter]%s' "$C" "$N"; read -r _; } || true; }
run()   { printf '%s$ %s%s\n' "$G" "$*" "$N"; eval "$@"; local rc=$?; pause; return $rc; }
show()  { # show FILE [first last]: print a file (or a line range) with line numbers
  local f="$1" a="${2:-1}" z="${3:-60}"
  printf '%s── %s (lines %s-%s)%s\n' "$C" "${f#"$ROOT/"}" "$a" "$z" "$N"
  if command -v bat >/dev/null; then bat --paging=never --style=numbers -r "$a:$z" "$f"
  else awk -v a="$a" -v z="$z" 'NR>=a && NR<=z {printf "%4d  %s\n", NR, $0}' "$f"; fi
  pause
}
grepx() { # grepx PATTERN FILE...: highlight the lines that matter
  printf '%s── grep -n "%s"%s\n' "$C" "$1" "$N"; grep -n --color=always -E "$1" "${@:2}"; pause
}
have() { command -v "$1" >/dev/null 2>&1; }
repo() { echo "$WORKSPACE/$1"; }
need_golden() {
  [[ -x "$GOLDEN" ]] || { printf '%sgolden CLI missing: run `make bootstrap` first%s\n' "$R" "$N"; exit 1; }
}

# ─────────────────────────────────────────────────────────────── preflight ──
preflight() {
  title "Preflight"
  local ok=1
  for t in git python3 jq docker kubectl helm terraform; do
    if have "$t"; then printf '  %s✓%s %s\n' "$G" "$N" "$t"; else printf '  %s✗%s %s\n' "$R" "$N" "$t"; ok=0; fi
  done
  for t in aws az gcloud kind kubectl-argo-rollouts bat; do
    have "$t" && printf '  %s✓%s %s\n' "$G" "$N" "$t" || printf '  %s-%s %s (optional)\n' "$Y" "$N" "$t"
  done
  [[ -x "$GOLDEN" ]] && printf '  %s✓%s golden CLI\n' "$G" "$N" || { printf '  %s✗%s golden CLI: run make bootstrap\n' "$R" "$N"; ok=0; }

  say "Sibling repos in $WORKSPACE"
  for r in nawex-ai-ml-infrastructure nawex-observability-case-study kubeflow-ml-pipeline mlflow-experiment-tracking openshift-k8s-ai-infra; do
    if [[ -d "$(repo "$r")" ]]; then printf '  %s✓%s %s\n' "$G" "$N" "$r"
    else printf '  %s✗%s %s  ->  git clone https://github.com/Here2ServeU/%s %s\n' "$R" "$N" "$r" "$r" "$(repo "$r")"; ok=0; fi
  done

  say "Cloud logins (needed for prep / live segments only)"
  have aws    && { aws sts get-caller-identity --query Account --output text 2>/dev/null | sed 's/^/  aws account: /' || echo "  aws: not logged in"; }
  have az     && { az account show --query name -o tsv 2>/dev/null | sed 's/^/  azure subscription: /' || echo "  azure: not logged in"; }
  have gcloud && echo "  gcp project: ${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"

  say "GPU quota: new accounts start at 0 GPUs on all three clouds. Request it days ahead:"
  echo "  AWS: Service Quotas > EC2 > 'Running On-Demand G and VT instances' (vCPUs, g5.xlarge needs 4)"
  echo "  Azure: Quotas > Compute > 'Standard NCASv3_T4 Family vCPUs' (NC4as_T4_v3 needs 4)"
  echo "  GCP: IAM & Admin > Quotas > 'NVIDIA T4 GPUs' in your region (1) and GPUS_ALL_REGIONS (1)"
  [[ "$ok" == "1" ]] && printf '\n%sReady to record.%s\n' "$G" "$N" || printf '\n%sFix the ✗ items above.%s\n' "$R" "$N"
}

# ──────────────────────────────────────────────────────────────────── prep ──
prep() {
  title "Prep: terraform plans with the GPU pool enabled (no resources created)"
  for c in $CLOUDS; do
    say "Planning $c (output -> $OUT/plan-$c.txt)"
    GPU_ENABLED=1 scripts/deploy.sh "$c" dev plan >"$OUT/plan-$c.txt" 2>&1 \
      && printf '  %s✓%s %s\n' "$G" "$N" "$c" \
      || printf '  %s✗%s %s: see %s\n' "$R" "$N" "$c" "$OUT/plan-$c.txt"
  done
}

# ────────────────────────────────────────────────── 1. GPU landing zones ──
clouds() {
  title "1 · One GPU landing zone, three clouds"
  say "Same contract on every cloud: a GPU pool that scales 0..N, tainted so only GPU work lands there."
  grepx 'gpu_node_groups|min_size|ami_type|nvidia.com/gpu' deploy/terraform/modules/aws/eks/main.tf
  grepx 'azurerm_kubernetes_cluster_node_pool" "gpu"|min_count|vm_size|node_taints' deploy/terraform/modules/azure/aks/main.tf
  grepx 'node_pool" "gpu"|min_node_count|guest_accelerator|gpu_driver_version|key    = "nvidia' deploy/terraform/modules/gcp/gke/main.tf
  say "One switch turns it on per environment:"
  grepx 'GPU_ENABLED|gpu_node_pool_enabled|gpu.enabled' scripts/deploy.sh
  for c in $CLOUDS; do
    if [[ -s "$OUT/plan-$c.txt" ]]; then
      say "terraform plan on $c (pre-run by 'prep'): GPU resources"
      grep -E 'will be created|Plan:' "$OUT/plan-$c.txt" | grep -iE 'gpu|Plan:' | head -8; pause
    else
      say "No saved plan for $c. Run: scripts/demo/ai-infra-demo.sh prep"
    fi
  done
  if [[ "$LIVE" == "1" ]]; then
    say "Live cluster: GPU nodes, labels and taints"
    run "kubectl get nodes -L nvidia.com/gpu.present -L node.kubernetes.io/instance-type"
  fi
}

# ──────────────────────────────────────────────────── 2. GPU node stack ──
gpu() {
  need_golden
  title "2 · GPU Operator, DCGM, MIG and time-slicing"
  show deploy/k8s/gpu-operator/README.md 18 40
  say "DCGM exporter is on, with a ServiceMonitor: GPU metrics flow into Prometheus."
  grepx 'dcgmExporter|serviceMonitor|interval|mig:|strategy' deploy/k8s/gpu-operator/clusterpolicy.yaml
  say "Time-slicing: one physical GPU is advertised as 4 schedulable GPUs."
  show deploy/k8s/gpu-operator/time-slicing-config.yaml 1 35
  say "MIG layouts the MIG manager can apply per node (label nvidia.com/mig.config=<layout>)."
  grepx 'all-disabled|all-1g|all-3g|inference-mixed|half-mig|devices|mig-devices' deploy/k8s/gpu-operator/mig-config.yaml
  say "Which sharing mode for which workload, and what it saves (prices are assumptions you pass in):"
  run "$GOLDEN gpu partition --gpu H100-80GB --price 6 | jq '{gpu_model, baseline_gpus, gpus_needed, gpus_saved, monthly_savings_usd, plan: [.gpus[] | {index, strategy, workloads, mig_layout}]}'"
  say "Alerting on GPU health and waste from DCGM metrics:"
  grepx 'alert:|DCGM_FI' observability/prometheus/rules/gpu_rules.yml
  if [[ "$LIVE" == "1" ]]; then
    run "kubectl -n gpu-operator get pods"
    run "kubectl get nodes -L nvidia.com/gpu.product -L nvidia.com/mig.config.state -L nvidia.com/gpu.replicas"
    run "kubectl describe nodes -l nvidia.com/gpu.present=true | grep -A7 Allocatable"
    say "Raw DCGM metrics straight from the exporter:"
    run "kubectl -n gpu-operator port-forward svc/nvidia-dcgm-exporter 9400:9400 >/dev/null 2>&1 & sleep 3; curl -s localhost:9400/metrics | grep -E '^DCGM_FI_DEV_(GPU_UTIL|FB_USED|GPU_TEMP)' | head; kill %1"
  fi
}

# ─────────────────────────────────────────────── 3. LLM & model serving ──
serving() {
  title "3 · LLM and model serving: autoscaling and canaries"
  say "KServe InferenceService: request-based autoscaling and a 10% canary."
  show deploy/k8s/ml-serving/inferenceservice.yaml 1 45
  say "vLLM (OpenAI-compatible) pinned to the GPU pool: node selector, toleration, 1 GPU."
  grepx 'nvidia.com/gpu|tolerations|image:|max-model-len|readinessProbe|/health' deploy/k8s/ml-serving/vllm.yaml
  say "Platform services ship as Argo Rollouts: 10% -> 25% -> 50%, judged by Prometheus."
  show deploy/helm/golden/values.yaml 337 365
  grepx 'successCondition|query:|failureLimit' deploy/helm/golden/templates/analysistemplate.yaml
  if have helm; then
    say "Rendered for AWS with rollouts on: the Rollout and its AnalysisTemplate"
    run "helm template golden deploy/helm/golden -f deploy/helm/golden/values-aws.yaml --set rollouts.enabled=true | grep -E '^kind: (Rollout|AnalysisTemplate)' | sort | uniq -c"
  fi
  if [[ "$LIVE" == "1" ]]; then
    run "kubectl get inferenceservice -A"
    have kubectl-argo-rollouts && run "kubectl argo rollouts list rollouts -A"
  fi
}

# ─────────────────────────────────────────────────────────────── 4. MLOps ──
mlops() {
  need_golden
  title "4 · MLOps: pipeline, registry, drift, gated promotion"
  local kfp; kfp="$(repo kubeflow-ml-pipeline)"
  if [[ -d "$kfp" ]]; then
    say "Kubeflow pipeline: load -> preprocess -> train -> evaluate -> deploy only above an accuracy threshold"
    grepx 'dsl.pipeline|def |threshold|Condition|If\(' "$kfp/pipeline.py"
    grepx 'threshold|accuracy' "$kfp/components/deploy.py"
  fi
  local reg="$OUT/registry"; rm -rf "$reg"
  say "Drift check (PSI + KS) on today's traffic vs the training baseline. Exit code 2 = drift."
  run "$GOLDEN model drift | jq '{drifted, features: [.features[] | {feature, psi, ks_statistic, p_value, band}]}'"
  say "Drift triggers a retrain. The first model becomes champion."
  run "$GOLDEN model retrain --force --registry $reg | jq '{action, alias, version, metrics}'"
  say "A retrain on new data registers a challenger, only if it passes the quality gate."
  run "$GOLDEN model retrain --force --registry $reg --seed 7 --scenario mixed | jq '{action, alias, version, metrics}'"
  say "Promotion needs a named approver AND must not be worse than the champion. Watch it refuse:"
  run "$GOLDEN model promote 2 --approver emmanuel --registry $reg"
  run "$GOLDEN model list --registry $reg | jq '.aliases'"
  local mlf; mlf="$(repo mlflow-experiment-tracking)"
  [[ -d "$mlf" ]] && { say "Same idea in MLflow: register the best run in the model registry."; grepx 'register_model|search_runs|order_by|transition|alias' "$mlf/src/register_best_model.py"; }
  local obs; obs="$(repo nawex-observability-case-study)"
  if [[ -d "$obs/demo" ]]; then
    say "Live option (laptop, kind): KServe + MLflow + drift simulator."
    echo "  cd $obs/demo && make up && make scenario-drift && make tab-grafana-drift"
    pause
  fi
}

# ─────────────────────────────────────────────────────────────── 5. SRE ──
sre() {
  title "5 · SRE: SLOs, OpenTelemetry, GitOps across clusters, chaos"
  say "SLOs as code, with multi-window burn-rate alerts (page fast burns, ticket slow ones)."
  grepx 'alert: |expr:|for:|severity' observability/prometheus/rules/slo_rules.yml
  local ai; ai="$(repo nawex-ai-ml-infrastructure)"
  if [[ -d "$ai" ]]; then
    say "One GitOps fleet: dev on EKS, staging on GKE, prod on AKS, reconciled from Git."
    run "ls $ai/argocd/clusters $ai/flux/clusters"
    run "ls $ai/terraform/modules"
    grepx 'objective|target|window|burn' "$ai/docs/slo-policy.md"
  fi
  local obs; obs="$(repo nawex-observability-case-study)"
  [[ -d "$obs" ]] && { say "One OpenTelemetry pipeline feeding Prometheus, Grafana and Splunk:"; run "ls $obs/observability/helm/otel-collector $obs/observability/alerting/prometheus-rules"; }
  say "Chaos drills that prove the alerts and the recovery path:"
  run "ls ops/sre/chaos"
  show ops/sre/chaos/pod-kill-test.sh 1 30
  if [[ "$LIVE" == "1" ]]; then
    run "bash ops/sre/chaos/pod-kill-test.sh"
  fi
}

case "${1:-help}" in
  preflight) preflight ;;
  prep)      prep ;;
  clouds)    clouds ;;
  gpu)       gpu ;;
  serving)   serving ;;
  mlops)     mlops ;;
  sre)       sre ;;
  all)       clouds; gpu; serving; mlops; sre ;;
  *)         sed -n '2,22p' "$0" ;;
esac
