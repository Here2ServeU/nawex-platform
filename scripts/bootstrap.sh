#!/usr/bin/env bash
# ===========================================================================
# NERP - Naweji Enterprise Reliability Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*"; }

info "Bootstrapping Naweji Reliability Platform (NRP)"

command -v node >/dev/null 2>&1 || { echo "Node.js is required."; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required."; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "pip3 is required."; exit 1; }

if command -v docker >/dev/null 2>&1; then
    info "Docker detected."
else
    warn "Docker not found. Robotics demo and containers will be unavailable."
fi

if command -v docker-compose >/dev/null 2>&1 || docker compose version >/dev/null 2>&1; then
    info "Docker Compose detected."
else
    warn "Docker Compose not found. Robotics demo will be unavailable."
fi

info "Installing app dependencies..."
npm --prefix "$REPO_ROOT/app" install

info "Setting up AI Python environment..."
AI_VENV="$REPO_ROOT/ai/.venv"
if [[ ! -d "$AI_VENV" ]]; then
    python3 -m venv "$AI_VENV"
fi

"$AI_VENV/bin/pip" install --upgrade pip
"$AI_VENV/bin/pip" install -r "$REPO_ROOT/ai/requirements.txt"

info "Bootstrap complete."
