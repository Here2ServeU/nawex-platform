#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if ! command -v trivy >/dev/null 2>&1; then
    echo "[container-scanning] trivy not installed"
    exit 1
fi

CONFIG_FILE="security/container-scanning/trivy.yaml"
IGNORE_FILE="security/container-scanning/trivy-ignore.txt"

IMAGES=(
    "nawex/app:ci"
    "nawex/fintech-core:ci"
    "nawex/fintech-fraud:ci"
    "nawex/fintech-gateway:ci"
    "nawex/healthcare-core:ci"
    "nawex/healthcare-clinical:ci"
    "nawex/healthcare-gateway:ci"
)

FAIL=0
for image in "${IMAGES[@]}"; do
    echo "[container-scanning] scanning $image"
    trivy image --config "$CONFIG_FILE" --ignorefile "$IGNORE_FILE" --exit-code 1 "$image" || FAIL=1
done

if [[ "$FAIL" -ne 0 ]]; then
    echo "[container-scanning] failed"
    exit 1
fi

echo "[container-scanning] passed"
