#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

APP_URL=${APP_URL:-"http://localhost:8080"}

curl -s -X POST "${APP_URL}/ops/heal" | jq .
