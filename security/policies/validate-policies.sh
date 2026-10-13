#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

FAIL=0

for required in \
security/policies/policy-controls.md \
security/policies/opa/k8s-security.rego \
security/policies/opa/aws-iam.rego \
security/identity/access-model.yaml

do
    if [[ ! -f "$required" ]]; then
        echo "[policies] missing required file: $required"
        FAIL=1
    fi
done

if command -v opa >/dev/null 2>&1; then
    echo "[policies] opa found, checking and testing rego"
    opa check security/policies/opa || FAIL=1
    opa test security/policies/opa || FAIL=1
else
    echo "[policies] opa not installed; skipping parse validation"
fi

if [[ "$FAIL" -ne 0 ]]; then
    echo "[policies] validation failed"
    exit 1
fi

echo "[policies] validation passed"
