#!/usr/bin/env bash
set -euo pipefail

# Unified platform startup for local enterprise demos.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run_if_exists() {
    local script_path="$1"
    if [[ -x "$script_path" ]]; then
        echo "[NERP] Starting $(basename "$script_path")"
        "$script_path"
        elif [[ -f "$script_path" ]]; then
        echo "[NERP] Starting $(basename "$script_path")"
        bash "$script_path"
    else
        echo "[NERP] Skipping missing script: $script_path"
    fi
}

run_if_exists "$ROOT_DIR/scripts/start_app.sh"
run_if_exists "$ROOT_DIR/scripts/start_ai.sh"
run_if_exists "$ROOT_DIR/scripts/start_fintech.sh"
run_if_exists "$ROOT_DIR/scripts/start_healthcare.sh"
run_if_exists "$ROOT_DIR/scripts/start_robotics.sh"

echo "[NERP] Platform startup sequence completed."
