#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f "$REPO_ROOT/docker-compose.yaml" up --build
else
    docker compose -f "$REPO_ROOT/docker-compose.yaml" up --build
fi
