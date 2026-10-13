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

# Override with IMAGES="img1 img2" (space separated); defaults to the three
# platform images built by CI (tag via IMAGE_TAG, default "ci").
IMAGE_TAG="${IMAGE_TAG:-ci}"
REGISTRY="${REGISTRY:-ghcr.io/here2serveu}"
if [[ -n "${IMAGES:-}" ]]; then
    read -r -a IMAGES <<< "$IMAGES"
else
    IMAGES=(
        "${REGISTRY}/golden-platform:${IMAGE_TAG}"
        "${REGISTRY}/golden-client-portal:${IMAGE_TAG}"
        "${REGISTRY}/golden-workload:${IMAGE_TAG}"
    )
fi

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
