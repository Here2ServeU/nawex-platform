#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

AI_VENV="$REPO_ROOT/ai/.venv"
if [[ ! -d "$AI_VENV" ]]; then
    echo "AI virtual environment not found. Run scripts/bootstrap.sh first." >&2
    exit 1
fi

"$AI_VENV/bin/python" -m ai.agents.orchestrator
