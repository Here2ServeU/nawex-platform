#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/here2serveu/golden-platform
# ===========================================================================
set -euo pipefail

# Configuration can be overridden via environment variables:
# e.g., LOCAL_PORT=8082 ./port-forward-aiops.sh
NAMESPACE="${NAMESPACE:-aiops}"
APP_LABEL="${APP_LABEL:-aiops-api}"
LOCAL_PORT="${LOCAL_PORT:-8081}"
CONTAINER_PORT=8080

echo "=================================================="
echo "[INFO] Looking for pod with label app=${APP_LABEL} in namespace ${NAMESPACE}..."
echo "=================================================="

POD=$(kubectl get pod -n "${NAMESPACE}" \
  -l "app=${APP_LABEL}" \
  -o jsonpath="{.items[0].metadata.name}" 2>/dev/null || true)

if [[ -z "${POD}" ]]; then
  echo "[ERROR] No pod found for app=${APP_LABEL} in namespace=${NAMESPACE}"
  exit 1
fi

echo "[INFO] Found pod: ${POD}"
echo "[INFO] Port-forwarding ${POD} localhost:${LOCAL_PORT}"
kubectl port-forward -n "${NAMESPACE}" "${POD}" "${LOCAL_PORT}":${CONTAINER_PORT}
