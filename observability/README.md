# observability

Full-stack observability for the Golden Platform, built on the **Grafana OSS stack**:
Prometheus · Alertmanager · Grafana · Loki · Promtail · Tempo (+ optional NVIDIA DCGM exporter).

## Architecture

```text
golden serve <service>  (api, transaction-engine, fraud-detector, payment-gateway,
                         ehr-ingestion, clinical-decision, patient-gateway,
                         gpu-optimizer, migration-planner)  + apps/ (client-portal, workload)
      │
      ├── /metrics ─────► Prometheus ──► Alertmanager ──► Slack / PagerDuty / email
      ├── logs ─────────► Promtail ──► Loki
      └── traces (OTLP) ► Tempo
                               │
                    Grafana ◄──┴── (Prometheus + Loki + Tempo datasources)
```

## Layout

```text
observability/
├── docker-compose.yml              # Prometheus, Alertmanager, Grafana, Loki, Promtail, Tempo (+ dcgm-exporter, profile "gpu")
├── prometheus/
│   ├── metrics_config.yaml         # Scrape jobs: platform-api, fintech, healthcare, gpu, migration, dcgm-exporter, apps
│   └── rules/
│       ├── golden_alerts.yml       # Availability, HTTP golden signals, fintech, healthcare, infra
│       ├── slo_rules.yml           # SLO recording rules + error-budget burn alerts
│       ├── ai_safety_rules.yml     # Kill switch, guardrail / blocked-action spikes, rate limiting, auth failures
│       ├── gpu_rules.yml           # Thermal > 85°C, idle GPUs, < 20% utilization, XID errors, savings
│       └── migration_rules.yml     # VM migration failures, stalled waves, duration
├── alerting/
│   ├── alertmanager.yml            # Routing tree, inhibition rules, receivers
│   ├── secrets/                    # Secret files (git-ignored) mounted into Alertmanager
│   └── templates/golden.tmpl
├── grafana/
│   ├── grafana.ini
│   ├── provisioning/{datasources,dashboards}
│   └── dashboards/
│       ├── golden-overview.json    # Platform-wide health, RED metrics, firing alerts
│       ├── golden-fintech.json     # Transactions, fraud score, payment latency
│       ├── golden-healthcare.json  # EHR ingestion, PHI risk, clinical decision
│       ├── golden-gpu.json         # GPU fleet utilization, thermals, idle GPUs, savings, DCGM
│       ├── golden-ai-safety.json   # Kill switch, guardrails, blocked actions, rate limiting
│       └── golden-migration.json   # VMware → OpenShift migration waves, failures, durations
├── loki/{loki-config.yaml,promtail-config.yaml}
└── tempo/tempo-config.yaml
```

## Quick start

```bash
docker compose up -d                                     # app stack (repo root)
docker compose -f observability/docker-compose.yml up -d # observability stack
docker compose -f observability/docker-compose.yml --profile gpu up -d   # + DCGM on NVIDIA hosts
open http://localhost:3000                               # Grafana (admin / golden-admin)
```

The observability stack joins the application network as an external network
(`${GOLDEN_NETWORK:-golden-platform_default}`) so Prometheus can resolve every
service by its compose DNS name. Set `GOLDEN_NETWORK` if your compose project
name differs (`docker network ls`).

| Variable | Description | Default |
|---|---|---|
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password | `golden-admin` |
| `GF_SECURITY_SECRET_KEY` | Grafana secret key (**set in production**) | dev value |
| `GOLDEN_NETWORK` | External docker network of the app stack | `golden-platform_default` |

Alertmanager does not expand environment variables, so notification secrets are
files under `alerting/secrets/` (git-ignored): `slack_webhook_url`,
`pagerduty_routing_key`, `smtp_password`.

## Metric contract

Every Python service exposes:

| Metric | Type | Labels |
|---|---|---|
| `golden_http_requests_total` | counter | service, method, path, status |
| `golden_http_request_duration_seconds` | histogram | service, method, path |
| `golden_fraud_score` | histogram | |
| `golden_transactions_total` | counter | status |
| `golden_ehr_records_total` | counter | status |
| `golden_phi_risk_score` | histogram | |
| `golden_gpu_utilization_ratio`, `golden_gpu_temperature_celsius` | gauge | gpu, node |
| `golden_gpu_idle_gpus`, `golden_gpu_projected_monthly_savings_usd` | gauge | |
| `golden_guardrail_rejections_total` | counter | service, reason |
| `golden_actions_blocked_total` | counter | reason |
| `golden_kill_switch_engaged` | gauge (0/1) | |
| `golden_rate_limited_total` | counter | service |
| `golden_migration_vms_total` | gauge/counter | status |
| `golden_migration_wave_progress_ratio` | gauge | wave |
| `golden_migration_failures_total` | counter | reason |
| `golden_migration_duration_seconds` | histogram | |

NVIDIA DCGM exporter metrics (`DCGM_FI_DEV_GPU_UTIL`, `DCGM_FI_DEV_GPU_TEMP`,
`DCGM_FI_DEV_FB_USED`, `DCGM_FI_DEV_POWER_USAGE`, `DCGM_FI_DEV_XID_ERRORS`)
are scraped from `dcgm-exporter:9400` in real GPU clusters.

## Alert routing

- **Critical** → PagerDuty + Slack `#golden-alerts`
- `vertical=fintech` → `#golden-fintech-alerts`; `vertical=healthcare` → `#golden-healthcare-alerts` (no PHI)
- `vertical=gpu` → `#golden-gpu-alerts`; `vertical=migration` → `#golden-migration-cutover`
- `domain=ai-safety` → `#golden-ai-safety`
- `slo=error_budget` → `#golden-slo-burn` + email

## Validation

```bash
promtool check config observability/prometheus/metrics_config.yaml
promtool check rules  observability/prometheus/rules/*.yml
amtool check-config   observability/alerting/alertmanager.yml
docker compose -f observability/docker-compose.yml config -q
```
