#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_URL=${APP_URL:-"http://localhost:8080"}

curl -s -X POST "${APP_URL}/ops/heal" | jq .
