#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# iam-policy-gate.sh - evaluate a Terraform plan against the AWS IAM guardrails
# in security/policies/opa/aws-iam.rego (the pipeline layer of the control-
# placement model; see docs/modernization/aws-iam-modernization.md).
#
#   scripts/iam-policy-gate.sh <terraform dir> [extra terraform plan args...]
#   scripts/iam-policy-gate.sh --plan-json plan.json
#
# Exits non-zero when any `deny` rule fires; `warn` results are printed only.
# Requires terraform (unless --plan-json) and opa.
# -----------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY_DIR="$REPO_ROOT/security/policies/opa"

command -v opa >/dev/null 2>&1 || { echo "opa is required: https://www.openpolicyagent.org/docs/#running-opa" >&2; exit 2; }
[[ $# -ge 1 ]] || { sed -n '2,/^# ----/p' "${BASH_SOURCE[0]}" | sed -e 's/^# \{0,1\}//' -e '/^----/d'; exit 2; }

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

if [[ "$1" == "--plan-json" ]]; then
  PLAN_JSON="${2:?--plan-json needs a file}"
else
  TF_DIR="$1"
  shift
  terraform -chdir="$TF_DIR" plan -input=false -lock=false -out="$TMP_DIR/tf.plan" "$@" >&2
  terraform -chdir="$TF_DIR" show -json "$TMP_DIR/tf.plan" >"$TMP_DIR/plan.json"
  PLAN_JSON="$TMP_DIR/plan.json"
fi

query() {
  opa eval --format raw -d "$POLICY_DIR" -i "$PLAN_JSON" \
    "concat(\"\\n\", sort([m | some m in data.golden.aws.iam.$1]))"
}

warnings="$(query warn)"
denials="$(query deny)"
[[ -n "$warnings" ]] && printf 'WARN  %s\n' "${warnings//$'\n'/$'\nWARN  '}"
if [[ -n "$denials" ]]; then
  printf 'DENY  %s\n' "${denials//$'\n'/$'\nDENY  '}"
  echo "iam-policy-gate: plan violates AWS IAM guardrails" >&2
  exit 1
fi
echo "iam-policy-gate: plan passes AWS IAM guardrails"
