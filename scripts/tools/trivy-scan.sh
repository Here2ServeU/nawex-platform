#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
set -euo pipefail

# Configuration
# NOTE: User must set the IMAGE environment variable before running.
# Example default updated to reflect the repository's focus (aiops-api).
IMAGE="${IMAGE:-"PLACEHOLDER_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/aiops-api:latest"}"
SEVERITY="${SEVERITY:-HIGH,CRITICAL,MEDIUM}"
# Set exit code to 1 if any vulnerabilities with the specified severity are found.
EXIT_CODE=1 

if ! command -v trivy >/dev/null 2>&1; then
  echo "[ERROR] Trivy not installed. See https://aquasecurity.github.io/trivy/"
  exit 1
fi

echo "===================================================="
echo "[INFO] Scanning image: ${IMAGE}"
echo "[INFO] Severity Threshold: ${SEVERITY}"
echo "===================================================="

# Run Trivy with policy enforcement. If vulnerabilities are found, the script will exit with code 1 due to --exit-code.
trivy image --severity "${SEVERITY}" --exit-code "${EXIT_CODE}" "${IMAGE}"

echo "===================================================="
echo "[SUCCESS] Image scan complete. No vulnerabilities found above ${SEVERITY} threshold."
echo "===================================================="
