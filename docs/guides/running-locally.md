# Running Locally

```bash
pip install -e ".[dev]"
golden serve api                    # :8000
golden serve transaction-engine     # :8090   (fintech)
golden serve fraud-detector         # :8091
golden serve ehr-ingestion          # :8093   (healthcare)
golden serve gpu-optimizer          # :8096   (GPU)
golden serve migration-planner      # :8097   (modernization)
```

Or everything at once with `docker compose up -d` from the repo root, plus
`docker compose -f observability/docker-compose.yml up -d` for Prometheus/Grafana.
See [quickstart.md](./quickstart.md).
