#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# validate-infra.sh - offline-ish validation of everything under deploy/ and
# security/. Runs locally (macOS/Linux) and in GitHub Actions (ubuntu-latest).
#
#   1. helm lint --strict + helm template | kubeconform for every chart
#      (default values, ci/*.yaml and values-*.yaml overlays)
#   2. kubeconform on deploy/k8s, deploy/openshift/manifests and deploy/gitops
#   3. kustomize build + kubeconform for deploy/openshift/virtualization
#   4. opa check/test for security/policies/opa (when opa is installed)
#   5. terraform fmt -check -recursive deploy/terraform
#   6. terraform init -backend=false + validate for every directory with *.tf
#
# Environment:
#   SKIP_TERRAFORM_VALIDATE=1  skip step 6 (fmt still runs)
#   SKIP_TERRAFORM=1           skip steps 5 and 6
#   SKIP_KUBERNETES=1          skip steps 1-4 (helm, manifests, kustomize, OPA)
#   KUBERNETES_VERSION         schema version for kubeconform (default 1.30.0)
#   KUBECONFORM_VERSION        version auto-downloaded when kubeconform is missing
#   TF_PLUGIN_CACHE_DIR        optional provider cache (recommended locally)
# Exit status is non-zero if any check fails; all checks run before exiting.
# -----------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

KUBERNETES_VERSION="${KUBERNETES_VERSION:-1.30.0}"
KUBECONFORM_VERSION="${KUBECONFORM_VERSION:-v0.6.7}"
FAILURES=()
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'; RED=$'\033[31m'; GREEN=$'\033[32m'; RESET=$'\033[0m'
else
  BOLD=""; RED=""; GREEN=""; RESET=""
fi

section() { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$RESET"; }
pass() { printf '%s  ok%s   %s\n' "$GREEN" "$RESET" "$1"; }
fail() { printf '%s  FAIL%s %s\n' "$RED" "$RESET" "$1"; FAILURES+=("$1"); }
need() { command -v "$1" >/dev/null 2>&1; }

# --------------------------------------------------------------- tooling -----
ensure_kubeconform() {
  if need kubeconform; then
    KUBECONFORM="$(command -v kubeconform)"
    return
  fi
  local os arch url
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  case "$arch" in
    x86_64 | amd64) arch="amd64" ;;
    arm64 | aarch64) arch="arm64" ;;
    *) echo "unsupported architecture for kubeconform: $arch" >&2; exit 2 ;;
  esac
  url="https://github.com/yannh/kubeconform/releases/download/${KUBECONFORM_VERSION}/kubeconform-${os}-${arch}.tar.gz"
  echo "kubeconform not found; downloading ${KUBECONFORM_VERSION} (${os}/${arch})"
  mkdir -p "$TMP_DIR/bin"
  curl -fsSL "$url" | tar -xz -C "$TMP_DIR/bin" kubeconform
  KUBECONFORM="$TMP_DIR/bin/kubeconform"
}

kubeconform_run() {
  "$KUBECONFORM" -strict -ignore-missing-schemas -summary \
    -kubernetes-version "$KUBERNETES_VERSION" "$@"
}

if [[ "${SKIP_KUBERNETES:-0}" == "1" ]]; then
  echo "SKIP_KUBERNETES=1: skipping helm, manifests, kustomize and OPA checks"
else
for tool in helm curl; do
  if ! need "$tool"; then
    echo "missing required tool: $tool" >&2
    exit 2
  fi
done
ensure_kubeconform

# ------------------------------------------------------------ helm charts ----
section "Helm charts (lint + template | kubeconform)"
for chart in deploy/helm/*/; do
  chart="${chart%/}"
  [[ -f "$chart/Chart.yaml" ]] || continue
  name="$(basename "$chart")"

  value_sets=("")
  shopt -s nullglob
  for f in "$chart"/ci/*.yaml "$chart"/values-*.yaml; do
    value_sets+=("$f")
  done
  shopt -u nullglob
  # OpenShift overrides live next to the OpenShift manifests.
  case "$name" in
    golden)
      value_sets+=(deploy/openshift/helm-values/golden-values.yaml
        deploy/openshift/helm-values/fintech-values.yaml
        deploy/openshift/helm-values/healthcare-values.yaml) ;;
    express-app)
      value_sets+=(deploy/openshift/helm-values/express-app-values.yaml) ;;
  esac

  for vf in "${value_sets[@]}"; do
    label="$name${vf:+ ($(basename "$vf"))}"
    args=()
    if [[ -n "$vf" ]]; then args=(-f "$vf"); fi
    out="$TMP_DIR/$name.out"
    if ! helm lint --strict "$chart" ${args[@]+"${args[@]}"} >"$out" 2>&1; then
      cat "$out"
      fail "helm lint $label"
      continue
    fi
    if ! helm template ci-release "$chart" --namespace ci ${args[@]+"${args[@]}"} \
        >"$TMP_DIR/$name.yaml" 2>"$out"; then
      cat "$out"
      fail "helm template $label"
      continue
    fi
    if kubeconform_run "$TMP_DIR/$name.yaml" >"$out" 2>&1; then
      pass "$label: $(tail -n1 "$out")"
    else
      cat "$out"
      fail "kubeconform $label"
    fi
  done
done

# ------------------------------------------------------ raw manifests --------
section "Raw manifests (kubeconform)"
for dir in deploy/k8s deploy/openshift/manifests deploy/gitops security/iam; do
  [[ -d "$dir" ]] || continue
  if kubeconform_run "$dir" >"$TMP_DIR/raw.out" 2>&1; then
    pass "$dir: $(tail -n1 "$TMP_DIR/raw.out")"
  else
    cat "$TMP_DIR/raw.out"
    fail "kubeconform $dir"
  fi
done

# ------------------------------------------------- kustomize overlays --------
section "Kustomize builds (kubeconform)"
kustomize_build() {
  if need kustomize; then
    kustomize build "$1"
  elif need kubectl; then
    kubectl kustomize "$1"
  else
    return 127
  fi
}
while IFS= read -r kfile; do
  kdir="$(dirname "$kfile")"
  # Only validate top-level kustomizations; nested ones are included by them.
  parent="$(dirname "$kdir")"
  if [[ -f "$parent/kustomization.yaml" ]]; then
    continue
  fi
  rc=0
  kustomize_build "$kdir" >"$TMP_DIR/kust.yaml" 2>"$TMP_DIR/kust.err" || rc=$?
  if [[ $rc -eq 127 ]]; then
    echo "  (kustomize/kubectl not installed; validating raw files in $kdir)"
    if kubeconform_run "$kdir" >"$TMP_DIR/kust.out" 2>&1; then
      pass "$kdir (raw): $(tail -n1 "$TMP_DIR/kust.out")"
    else
      cat "$TMP_DIR/kust.out"
      fail "kubeconform $kdir"
    fi
  elif [[ $rc -ne 0 ]]; then
    cat "$TMP_DIR/kust.err"
    fail "kustomize build $kdir"
  elif kubeconform_run "$TMP_DIR/kust.yaml" >"$TMP_DIR/kust.out" 2>&1; then
    pass "$kdir: $(tail -n1 "$TMP_DIR/kust.out")"
  else
    cat "$TMP_DIR/kust.out"
    fail "kubeconform $kdir"
  fi
done < <(find deploy/openshift/virtualization deploy/gitops -name kustomization.yaml | sort)

# ----------------------------------------------------------- policies --------
section "OPA policies"
if need opa; then
  if opa check security/policies/opa && opa test security/policies/opa >"$TMP_DIR/opa.out" 2>&1; then
    pass "security/policies/opa: $(tail -n1 "$TMP_DIR/opa.out")"
  else
    cat "$TMP_DIR/opa.out" 2>/dev/null || true
    fail "opa check/test security/policies/opa"
  fi
else
  echo "  (opa not installed; skipping)"
fi
fi  # SKIP_KUBERNETES

# ---------------------------------------------------------- terraform --------
if [[ "${SKIP_TERRAFORM:-0}" == "1" ]]; then
  echo
  echo "SKIP_TERRAFORM=1: skipping terraform checks"
elif ! need terraform; then
  fail "terraform not installed (set SKIP_TERRAFORM=1 to skip)"
else
  section "Terraform fmt"
  if terraform fmt -check -recursive -diff deploy/terraform; then
    pass "terraform fmt -check -recursive deploy/terraform"
  else
    fail "terraform fmt (run: terraform fmt -recursive deploy/terraform)"
  fi

  if [[ "${SKIP_TERRAFORM_VALIDATE:-0}" == "1" ]]; then
    echo "SKIP_TERRAFORM_VALIDATE=1: skipping terraform validate"
  else
    section "Terraform validate"
    export TF_IN_AUTOMATION=1
    if [[ -n "${TF_PLUGIN_CACHE_DIR:-}" ]]; then
      mkdir -p "$TF_PLUGIN_CACHE_DIR"
    fi
    while IFS= read -r tfdir; do
      if terraform -chdir="$tfdir" init -backend=false -input=false -upgrade -no-color \
          >"$TMP_DIR/tf.out" 2>&1 \
        && terraform -chdir="$tfdir" validate -no-color >>"$TMP_DIR/tf.out" 2>&1; then
        pass "$tfdir"
      else
        cat "$TMP_DIR/tf.out"
        fail "terraform validate $tfdir"
      fi
    done < <(find deploy/terraform -name '*.tf' -not -path '*/.terraform/*' -exec dirname {} \; | sort -u)
  fi
fi

# ------------------------------------------------------------ summary --------
echo
if [[ ${#FAILURES[@]} -gt 0 ]]; then
  printf '%s%d check(s) failed:%s\n' "$RED" "${#FAILURES[@]}" "$RESET"
  printf '  - %s\n' "${FAILURES[@]}"
  exit 1
fi
printf '%sAll infrastructure checks passed.%s\n' "$GREEN" "$RESET"
