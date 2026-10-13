# Developer Setup

1. Install Python 3.11+, Docker (Compose v2) and Node.js 18+.
2. `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
   (add `ml` for torch — [gpu-acceleration.md](./gpu-acceleration.md)).
3. Run the tests: `pytest`.
4. Start the stack: `docker compose up -d` (and `docker compose -f observability/docker-compose.yml up -d`).
5. Validate health: `curl -s localhost:8000/health` or open Grafana at http://localhost:3000.
6. Lint shell scripts: `shellcheck -S warning ops/**/*.sh tools/**/*.sh scripts/tools/*.sh`.
