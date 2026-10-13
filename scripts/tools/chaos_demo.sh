#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/here2serveu/golden-platform
# ===========================================================================
set -euo pipefail

APP_URL=${APP_URL:-"http://localhost:8080"}

curl -s -X POST "${APP_URL}/chaos/latency" -H 'Content-Type: application/json' -d '{"delay": 700}' | jq .
curl -s -X POST "${APP_URL}/chaos/error-spike" | jq .
curl -s -X POST "${APP_URL}/chaos/cpu" | jq .
curl -s "${APP_URL}/chaos/stress-test?intensity=1" | jq .
