#!/usr/bin/env bash
# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
set -euo pipefail

AIOPS_URL=${AIOPS_URL:-"http://localhost:8080/finops"}

echo "[INFO] Sending FinOps test request to ${AIOPS_URL}"

curl -X POST "${AIOPS_URL}" \
  -H "Content-Type: application/json" \
  -d '{
        "cpu_millicores": 600,
        "memory_mb": 700,
        "hours_per_month": 720,
        "node_hourly_price": 0.12
      }' | jq .
