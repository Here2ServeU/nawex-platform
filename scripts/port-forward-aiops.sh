#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=${NAMESPACE:-aiops}
SERVICE=${SERVICE:-aiops-api}
LOCAL_PORT=${LOCAL_PORT:-8080}
REMOTE_PORT=${REMOTE_PORT:-80}

echo "[INFO] Port-forwarding ${SERVICE} in ${NAMESPACE} to localhost:${LOCAL_PORT}"
kubectl port-forward svc/${SERVICE} -n ${NAMESPACE} ${LOCAL_PORT}:${REMOTE_PORT}
