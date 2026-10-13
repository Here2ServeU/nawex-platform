#!/usr/bin/env bash
# ===========================================================================
# Golden Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/nawex-platform
# ===========================================================================
set -euo pipefail

APP_URL=${APP_URL:-"http://localhost:8080"}

curl -s -X POST "${APP_URL}/ops/heal" | jq .
