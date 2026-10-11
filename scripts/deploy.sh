#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# deploy.sh - one command to stand up the Golden platform.
#
#   scripts/deploy.sh <aws|azure|gcp|openshift|local> <env> [plan|apply|destroy] [options]
#
#   aws|azure|gcp  terraform (deploy/terraform/live/<cloud>/<env>) -> kubeconfig
#                  -> helm upgrade --install golden (values-<cloud>.yaml)
#   openshift      uses the current `oc` login; Helm only (values-openshift.yaml)
#   local          kind cluster "golden" (created if missing); values-local.yaml
#
# Options:
#   --dry-run       print every command instead of running it
#   --yes, -y       do not ask for confirmation before apply/destroy
#   --local-state   allow terraform without backend.hcl (writes backend_override.tf
#                   that forces local state; for demos only)
#   -h, --help      show this help
#
# Environment:
#   IMAGE_TAG       image tag to deploy (default: latest)
#   GPU_ENABLED=1   create the GPU node pool and schedule gpu-optimizer on it
#   GCP_PROJECT     GCP project ID (passed as -var project_id; or set it in terraform.tfvars)
#   RELEASE         Helm release name (default: golden)
#   NAMESPACE       Kubernetes namespace (default: golden)
#   EXTRA_HELM_ARGS extra arguments appended to helm upgrade (word-split)
# -----------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHART_DIR="$REPO_ROOT/deploy/helm/golden"
RELEASE="${RELEASE:-golden}"
NAMESPACE="${NAMESPACE:-golden}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
GPU_ENABLED="${GPU_ENABLED:-0}"
KIND_CLUSTER="${KIND_CLUSTER:-golden}"

DRY_RUN=0
ASSUME_YES=0
LOCAL_STATE=0
POSITIONAL=()

usage() {
  sed -n '2,/^# ----/p' "${BASH_SOURCE[0]}" | sed -e 's/^# \{0,1\}//' -e '/^----/d'
}

die() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

log() { printf '\n==> %s\n' "$*"; }

# Print (dry-run) or execute a command given as separate arguments.
run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

confirm() {
  [[ "$ASSUME_YES" == "1" || "$DRY_RUN" == "1" ]] && return 0
  local reply
  read -r -p "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]([Ee][Ss])?$ ]]
}

# --------------------------------------------------------------- arguments ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    -y | --yes) ASSUME_YES=1 ;;
    --local-state) LOCAL_STATE=1 ;;
    -h | --help) usage; exit 0 ;;
    -*) die "unknown option: $1 (see --help)" ;;
    *) POSITIONAL+=("$1") ;;
  esac
  shift
done

[[ ${#POSITIONAL[@]} -ge 2 ]] || { usage; exit 2; }
CLOUD="${POSITIONAL[0]}"
ENVIRONMENT="${POSITIONAL[1]}"
ACTION="${POSITIONAL[2]:-apply}"

case "$CLOUD" in
  aws | azure | gcp | openshift | local) ;;
  *) die "cloud must be one of: aws azure gcp openshift local (got '$CLOUD')" ;;
esac
case "$ACTION" in
  plan | apply | destroy) ;;
  *) die "action must be plan, apply or destroy (got '$ACTION')" ;;
esac
if [[ "$CLOUD" =~ ^(aws|azure|gcp)$ && ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
  die "env must be dev, staging or prod for $CLOUD (got '$ENVIRONMENT')"
fi

TF_DIR="$REPO_ROOT/deploy/terraform/live/$CLOUD/$ENVIRONMENT"
VALUES_FILE="$CHART_DIR/values-$CLOUD.yaml"

# ----------------------------------------------------------- prerequisites ---
declare -a MISSING=()
require() {
  local tool="$1" hint="$2"
  if ! command -v "$tool" >/dev/null 2>&1; then
    MISSING+=("$tool: $hint")
  fi
}

require helm "https://helm.sh/docs/intro/install/ (brew install helm)"
require kubectl "https://kubernetes.io/docs/tasks/tools/ (brew install kubectl)"
case "$CLOUD" in
  aws)
    require terraform "https://developer.hashicorp.com/terraform/install"
    require aws "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html" ;;
  azure)
    require terraform "https://developer.hashicorp.com/terraform/install"
    require az "https://learn.microsoft.com/cli/azure/install-azure-cli" ;;
  gcp)
    require terraform "https://developer.hashicorp.com/terraform/install"
    require gcloud "https://cloud.google.com/sdk/docs/install (plus: gcloud components install gke-gcloud-auth-plugin)" ;;
  openshift)
    require oc "https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html" ;;
  local)
    require kind "https://kind.sigs.k8s.io/docs/user/quick-start/#installation (brew install kind)"
    require docker "https://docs.docker.com/get-docker/ (kind needs a container runtime)" ;;
esac

if [[ ${#MISSING[@]} -gt 0 ]]; then
  printf 'missing prerequisites:\n' >&2
  printf '  - %s\n' "${MISSING[@]}" >&2
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '(continuing because of --dry-run)\n' >&2
  else
    exit 1
  fi
fi

[[ -f "$VALUES_FILE" ]] || die "values overlay not found: $VALUES_FILE"

# --------------------------------------------------------------- terraform ---
tf() { run terraform -chdir="$TF_DIR" "$@"; }

TF_VARS=()
if [[ "$GPU_ENABLED" == "1" ]]; then
  TF_VARS+=(-var "gpu_node_pool_enabled=true")
fi
if [[ "$CLOUD" == "gcp" && -n "${GCP_PROJECT:-}" ]]; then
  TF_VARS+=(-var "project_id=$GCP_PROJECT")
fi

terraform_init() {
  [[ -d "$TF_DIR" ]] || die "terraform directory not found: $TF_DIR"
  local init_args=(-input=false)
  if [[ -f "$TF_DIR/backend.hcl" ]]; then
    init_args+=(-backend-config=backend.hcl)
  elif [[ "$DRY_RUN" == "1" && "$LOCAL_STATE" != "1" ]]; then
    printf 'note: %s/backend.hcl does not exist yet (copy backend.hcl.example)\n' "$TF_DIR" >&2
    init_args+=(-backend-config=backend.hcl)
  elif [[ "$LOCAL_STATE" == "1" ]]; then
    printf 'warning: no backend.hcl; forcing LOCAL state via backend_override.tf\n' >&2
    if [[ "$DRY_RUN" == "1" ]]; then
      printf '+ write %s\n' "$TF_DIR/backend_override.tf"
    else
      printf 'terraform {\n  backend "local" {}\n}\n' >"$TF_DIR/backend_override.tf"
    fi
  else
    die "no $TF_DIR/backend.hcl. Copy backend.hcl.example to backend.hcl (remote state), or pass --local-state for a throwaway demo."
  fi
  log "terraform init ($CLOUD/$ENVIRONMENT)"
  tf init "${init_args[@]}"
}

# Read a terraform output, or a placeholder in dry-run mode.
tf_output() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '<%s>' "$1"
  else
    terraform -chdir="$TF_DIR" output -raw "$1"
  fi
}

# Run the kubeconfig command reported by terraform (a plain command string).
configure_kubeconfig() {
  local cmd_string
  cmd_string="$(tf_output kubeconfig_command)"
  log "configure kubectl: $cmd_string"
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '+ %s\n' "$cmd_string"
  else
    local -a cmd
    read -r -a cmd <<<"$cmd_string"
    "${cmd[@]}"
  fi
}

# ----------------------------------------------------------------- helm ------
HELM_SET=()

identity_annotation_key() {
  case "$CLOUD" in
    aws) printf '%s' 'eks\.amazonaws\.com/role-arn' ;;
    azure) printf '%s' 'azure\.workload\.identity/client-id' ;;
    gcp) printf '%s' 'iam\.gke\.io/gcp-service-account' ;;
  esac
}

helm_deploy() {
  local args=(upgrade --install "$RELEASE" "$CHART_DIR"
    --namespace "$NAMESPACE" --create-namespace
    -f "$VALUES_FILE"
    --set-string "image.tag=$IMAGE_TAG"
    --wait --timeout 15m)
  if [[ -f "$CHART_DIR/values-$CLOUD-$ENVIRONMENT.yaml" ]]; then
    args+=(-f "$CHART_DIR/values-$CLOUD-$ENVIRONMENT.yaml")
  fi
  if [[ "$GPU_ENABLED" == "1" ]]; then
    args+=(--set gpu.enabled=true)
  fi
  if [[ ${#HELM_SET[@]} -gt 0 ]]; then
    args+=("${HELM_SET[@]}")
  fi
  if [[ -n "${EXTRA_HELM_ARGS:-}" ]]; then
    local -a extra
    read -r -a extra <<<"$EXTRA_HELM_ARGS"
    args+=("${extra[@]}")
  fi
  log "helm upgrade --install $RELEASE (namespace $NAMESPACE)"
  run helm "${args[@]}"
  if [[ "$DRY_RUN" != "1" ]]; then
    kubectl -n "$NAMESPACE" get deploy,svc -l "app.kubernetes.io/instance=$RELEASE"
  fi
}

helm_uninstall() {
  log "helm uninstall $RELEASE"
  run helm uninstall "$RELEASE" --namespace "$NAMESPACE" --ignore-not-found --wait
}

# ------------------------------------------------------------- workflows -----
cloud_flow() {
  terraform_init
  case "$ACTION" in
    plan)
      log "terraform plan"
      tf plan -input=false ${TF_VARS[@]+"${TF_VARS[@]}"}
      ;;
    apply)
      log "terraform plan"
      tf plan -input=false -out=golden.tfplan ${TF_VARS[@]+"${TF_VARS[@]}"}
      confirm "Apply this plan to $CLOUD/$ENVIRONMENT?" || die "aborted"
      log "terraform apply"
      tf apply -input=false golden.tfplan
      configure_kubeconfig
      local registry identity
      registry="$(tf_output registry_url)"
      identity="$(tf_output workload_identity)"
      HELM_SET+=(--set-string "image.registry=$registry")
      HELM_SET+=(--set-string "serviceAccount.annotations.$(identity_annotation_key)=$identity")
      helm_deploy
      ;;
    destroy)
      confirm "DESTROY the $CLOUD/$ENVIRONMENT environment (cluster, registry, network)?" || die "aborted"
      if [[ "$DRY_RUN" == "1" ]] || terraform -chdir="$TF_DIR" output -raw kubeconfig_command >/dev/null 2>&1; then
        configure_kubeconfig || true
        helm_uninstall || true
      fi
      log "terraform destroy"
      tf destroy -input=false -auto-approve ${TF_VARS[@]+"${TF_VARS[@]}"}
      ;;
  esac
}

openshift_flow() {
  if [[ "$DRY_RUN" != "1" ]]; then
    oc whoami >/dev/null 2>&1 || die "not logged in to OpenShift: run 'oc login --server=<api-url>' first"
  fi
  local server="<current oc context>"
  if [[ "$DRY_RUN" != "1" ]]; then
    server="$(oc whoami --show-server)"
  fi
  log "OpenShift cluster: $server"
  case "$ACTION" in
    plan)
      run helm template "$RELEASE" "$CHART_DIR" --namespace "$NAMESPACE" -f "$VALUES_FILE" --set-string "image.tag=$IMAGE_TAG"
      ;;
    apply)
      confirm "Deploy $RELEASE to OpenShift namespace $NAMESPACE?" || die "aborted"
      helm_deploy
      ;;
    destroy)
      confirm "Uninstall $RELEASE from OpenShift namespace $NAMESPACE?" || die "aborted"
      helm_uninstall
      ;;
  esac
}

local_flow() {
  case "$ACTION" in
    plan)
      run helm template "$RELEASE" "$CHART_DIR" --namespace "$NAMESPACE" -f "$VALUES_FILE" --set-string "image.tag=$IMAGE_TAG"
      ;;
    apply)
      if [[ "$DRY_RUN" == "1" ]] || ! kind get clusters 2>/dev/null | grep -qx "$KIND_CLUSTER"; then
        log "creating kind cluster $KIND_CLUSTER"
        run kind create cluster --name "$KIND_CLUSTER" --wait 120s
      fi
      run kubectl config use-context "kind-$KIND_CLUSTER"
      helm_deploy
      local api_svc="$RELEASE-golden-api"
      [[ "$RELEASE" == *golden* ]] && api_svc="$RELEASE-api"
      printf '\nTry it: kubectl -n %s port-forward svc/%s 8000:8000 && curl localhost:8000/health\n' "$NAMESPACE" "$api_svc"
      ;;
    destroy)
      helm_uninstall || true
      confirm "Delete kind cluster $KIND_CLUSTER?" && run kind delete cluster --name "$KIND_CLUSTER"
      ;;
  esac
}

log "golden deploy: cloud=$CLOUD env=$ENVIRONMENT action=$ACTION image.tag=$IMAGE_TAG$( [[ "$DRY_RUN" == "1" ]] && echo ' (dry-run)')"
case "$CLOUD" in
  aws | azure | gcp) cloud_flow ;;
  openshift) openshift_flow ;;
  local) local_flow ;;
esac
log "done"
