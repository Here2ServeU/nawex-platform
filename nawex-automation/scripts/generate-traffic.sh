#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
set -euo pipefail

# Default URL points to the external Ingress hostname for the Express Web App
# NOTE: For local testing, override with: export APP_URL="http://127.0.0.1:8080"
APP_URL=${APP_URL:-"http://express-web-app.nrp-platform.com"}
CONCURRENCY=${CONCURRENCY:-50}
REQUESTS=${REQUESTS:-20000}

echo "=================================================="
echo "[INFO] Generating traffic to Express Web App: ${APP_URL} ..."
echo "[INFO] Concurrency: ${CONCURRENCY}, Requests: ${REQUESTS}"
echo "=================================================="
echo "[INFO] Using hey if installed, otherwise curl in a loop."

if command -v hey >/dev/null 2>&1; then
  hey -n ${REQUESTS} -c ${CONCURRENCY} "${APP_URL}"
else
  for i in $(seq 1 ${REQUESTS}); do
    curl -s -o /dev/null "${APP_URL}" &
    if (( i % 100 == 0 )); then
      wait
    fi
  done
  wait
fi
echo "[INFO] Traffic generation complete."
