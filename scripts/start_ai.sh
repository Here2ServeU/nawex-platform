#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

AI_VENV="$REPO_ROOT/ai/.venv"
if [[ ! -d "$AI_VENV" ]]; then
    echo "AI virtual environment not found. Run scripts/bootstrap.sh first." >&2
    exit 1
fi

"$AI_VENV/bin/python" -m ai.agents.orchestrator
