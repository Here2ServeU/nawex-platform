#!/usr/bin/env bash
# ===========================================================================
# NAWEX - Nawex Platform
# Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.
# https://github.com/Here2ServeU/Naweji-Reliability-Platform
# ===========================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$REPO_ROOT/logs"
APP_URL=${APP_URL:-"http://localhost:8080"}
BOOTSTRAP=${BOOTSTRAP:-1}
DEMO_CHAOS=${DEMO_CHAOS:-1}
DEMO_ROBOTICS=${DEMO_ROBOTICS:-0}
DETACH=${DETACH:-1}

mkdir -p "$LOG_DIR"

info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*"; }

info "Ensuring scripts are executable..."
chmod +x "$REPO_ROOT/scripts"/*.sh || true

if [[ "$BOOTSTRAP" == "1" ]]; then
    info "Running bootstrap..."
    bash "$REPO_ROOT/scripts/bootstrap.sh"
fi

info "Starting Express app..."
nohup npm --prefix "$REPO_ROOT/app" start > "$LOG_DIR/app.log" 2>&1 &
APP_PID=$!

info "Starting AIOps orchestrator..."
AI_VENV="$REPO_ROOT/ai/.venv"
"$AI_VENV/bin/python" -m ai.agents.orchestrator > "$LOG_DIR/ai.log" 2>&1 &
AI_PID=$!

if [[ "$DEMO_ROBOTICS" == "1" ]]; then
    info "Starting robotics demo (detached)..."
    if command -v docker-compose >/dev/null 2>&1; then
        docker-compose -f "$REPO_ROOT/docker-compose.yaml" up --build -d
    else
        docker compose -f "$REPO_ROOT/docker-compose.yaml" up --build -d
    fi
fi

info "Waiting for app to become healthy..."
for i in {1..30}; do
    if curl -s "$APP_URL/metrics" >/dev/null 2>&1; then
        info "App is healthy at $APP_URL"
        break
    fi
    sleep 1
    if [[ $i -eq 30 ]]; then
        warn "App did not become healthy in time. Check logs/app.log"
    fi
done

if [[ "$DEMO_CHAOS" == "1" ]]; then
    info "Triggering chaos demo..."
    bash "$REPO_ROOT/scripts/chaos_demo.sh" || true
fi

info "Demo is running. Logs: $LOG_DIR/app.log and $LOG_DIR/ai.log"

if [[ "$DETACH" == "1" ]]; then
    info "Services are running in background. To stop:"
    info " kill $APP_PID $AI_PID"
    exit 0
fi

cleanup() {
    info "Stopping demo..."
    kill "$APP_PID" "$AI_PID" 2>/dev/null || true
}
trap cleanup EXIT

wait
