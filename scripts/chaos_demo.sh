#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_URL=${APP_URL:-"http://localhost:8080"}

curl -s -X POST "${APP_URL}/chaos/latency" -H 'Content-Type: application/json' -d '{"delay": 700}' | jq .
curl -s -X POST "${APP_URL}/chaos/error-spike" | jq .
curl -s -X POST "${APP_URL}/chaos/cpu" | jq .
curl -s "${APP_URL}/chaos/stress-test?intensity=1" | jq .
