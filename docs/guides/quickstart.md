# Quickstart

Bring up the Golden Platform locally, run the demos and see it in Grafana.

## Prerequisites

- Python 3.11+, Docker with Compose v2, Node.js 18+ (only for `apps/`), `jq`

## 1) Install the package and CLI

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # add ,ml for torch training — see guides/gpu-acceleration.md
golden --help
```

## 2) Run a demo without containers

```bash
golden demo client --vertical hospital --client "General Hospital" --fast
golden demo client --vertical bank --client "Acme Bank" --fast
golden demo client --vertical gpu --client "Acme AI" --fast
golden demo engine --epochs 1
golden roi --vertical healthcare --tier professional
golden security status
```

## 3) Run services

Single service on the host:

```bash
golden serve fraud-detector        # http://localhost:8091/health
```

Full stack (one image, every service) from the repo root:

```bash
docker compose up -d
docker compose -f observability/docker-compose.yml up -d
open http://localhost:3000         # Grafana (admin / golden-admin)
```

| Service | Port | Key route |
|---|---|---|
| api | 8000 | `POST /v1/fraud/score`, `/v1/decisions`, `/v1/roi/{vertical}` |
| transaction-engine | 8090 | `POST /api/v1/transactions` |
| fraud-detector | 8091 | `POST /score` |
| payment-gateway | 8092 | |
| ehr-ingestion | 8093 | `POST /api/v1/ehr/ingest` |
| clinical-decision | 8094 | |
| patient-gateway | 8095 | |
| gpu-optimizer | 8096 | `POST /api/v1/gpu/analyze` |
| migration-planner | 8097 | `POST /api/v1/migration/assess\|plan\|manifests` |
| client-portal / workload | 3001 / 8080 | Node apps |

All services expose `/health`, `/ready`, `/metrics`. When `GOLDEN_API_KEYS` is set, send `X-API-Key`.

## 4) Exercise the APIs

```bash
curl -s localhost:8000/health | jq
curl -s -X POST localhost:8091/score -H 'Content-Type: application/json' \
  -H "X-API-Key: ${GOLDEN_API_KEY:-dev-key}" \
  -d '{"transaction_id":"txn_123","amount":150.00,"sender":"acct_001","receiver":"acct_002"}' | jq
```

More requests: `tools/http/aiops.http` (VS Code REST Client / JetBrains HTTP client).
Load tests: `k6 run tools/k6/load-test.js`, `k6 run tools/k6/transaction-load.js`.

## 5) AI orchestration & chaos

```bash
golden orchestrate --cycles 3                         # dry_run by default — see security/ai-safety.md
ops/sre/chaos/payment-gateway-failure.sh
ops/sre/chaos/transaction-fraud-spike.sh
ops/sre/chaos/ehr-gateway-failure.sh
ops/sre/chaos/phi-breach-simulation.sh
```

The orchestrator config lives in `src/golden/ai/agents/agent_config.yaml`.

## Legacy scripts

The pre-monorepo helper scripts (`bootstrap.sh`, `start_*.sh`, `healthcheck.sh`, `chaos_demo.sh`, …) are kept
under `scripts/tools/` for reference; prefer the `golden` CLI and `docker compose`.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
