# nawex-observability

Full-stack observability layer for the NAWEX platform, built on the **Grafana OSS stack**:
Prometheus · Alertmanager · Grafana · Loki · Promtail · Tempo

---

## Architecture

```
Services (nawex-api, fintech-*, healthcare-*, robotics-*)
      │
      ├── metrics ──────► Prometheus ──► Alertmanager ──► Slack / PagerDuty
      │                        │
      │                        └──► Tempo (span-metrics, service-graph)
      │
      ├── logs ─────────► Promtail ──► Loki
      │
      └── traces ───────► Tempo (OTLP / Jaeger / Zipkin)
                               │
                    Grafana ◄──┴──── (Prometheus + Loki + Tempo datasources)
```

---

## Directory Structure

```
nawex-observability/
├── docker-compose.yml          # Spin up the full stack locally
├── prometheus/
│   ├── metrics_config.yaml     # Scrape config for all NAWEX services
│   └── rules/
│       ├── nawex_alerts.yml     # Service, fintech, healthcare & infra alerts
│       └── slo_rules.yml       # SLO recording rules + error-budget burn alerts
├── alerting/
│   ├── alertmanager.yml        # Routing tree, inhibition rules, receivers
│   └── templates/
│       └── nawex.tmpl           # Slack / email notification templates
├── grafana/
│   ├── grafana.ini             # Grafana server configuration
│   ├── provisioning/
│   │   ├── datasources/        # Auto-provisioned Prometheus, Loki, Tempo
│   │   └── dashboards/         # Dashboard provider config
│   └── dashboards/
│       ├── nawex-overview.json  # Platform-wide health & SLO dashboard
│       ├── nawex-fintech.json   # Fintech transactions, fraud, payments
│       └── nawex-healthcare.json# EHR ingestion, clinical decision, compliance
├── loki/
│   ├── loki-config.yaml        # Loki server (TSDB backend, 31-day retention)
│   └── promtail-config.yaml    # Log scraping per service + PHI redaction
├── tempo/
│   └── tempo-config.yaml       # Distributed tracing (OTLP, Jaeger, Zipkin)
└── logging/
    └── log_pipeline.py         # Python log pipeline: parse → enrich → ship to Loki
```

---

## Quick Start

```bash
# Start the full observability stack
docker compose up -d

# Check service health
docker compose ps

# Tail Loki logs
docker compose logs -f loki

# Open Grafana (admin / nawex-admin)
open http://localhost:3000
```

Environment variables (copy `.env.example` or export directly):

| Variable | Description | Required |
|---|---|---|
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password | No (default: `nawex-admin`) |
| `GF_SECURITY_SECRET_KEY` | Grafana secret key | **Yes** in production |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook | No |
| `PAGERDUTY_ROUTING_KEY` | PagerDuty Events API v2 key | No |
| `SMTP_PASSWORD` | SMTP auth password for email alerts | No |

---

## Ports

| Service | Port | Protocol |
|---|---|---|
| Prometheus | 9090 | HTTP |
| Alertmanager | 9093 | HTTP |
| Grafana | 3000 | HTTP |
| Loki | 3100 | HTTP |
| Tempo HTTP | 3200 | HTTP |
| Tempo OTLP gRPC | 4317 | gRPC |
| Tempo OTLP HTTP | 4318 | HTTP |
| Tempo Jaeger HTTP | 14268 | HTTP |
| Tempo Zipkin | 9411 | HTTP |

---

## Instrumenting Services

### Metrics (Prometheus)
Services must expose a `/metrics` endpoint compatible with Prometheus' text format.
For Python services use `prometheus_client`; for Node.js use `prom-client`.

### Traces (OpenTelemetry)
Send traces to `http://tempo:4318/v1/traces` (HTTP) or `tempo:4317` (gRPC).

```python
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

exporter = OTLPSpanExporter(endpoint="http://tempo:4318/v1/traces")
```

### Logs (Loki via log_pipeline)
```python
from logging.log_pipeline import LokiShipper

shipper = LokiShipper()
shipper.push({"message": "payment processed", "service": "payment-gateway",
              "vertical": "fintech", "level": "INFO", "traceID": "abc123"})
```

---

## Alerting

Alerts are defined in `prometheus/rules/` and routed via `alerting/alertmanager.yml`:

- **Critical** → PagerDuty + Slack `#nawex-alerts`
- **Fintech** → Slack `#nawex-fintech-alerts`
- **Healthcare** → Slack `#nawex-healthcare-alerts` (no PHI in messages)
- **SLO burn** → Slack `#nawex-slo-burn` + email to SRE team

SLOs enforced:
- Availability ≥ 99.9% (5-min window)
- p95 latency < 500ms
- Error budget burn alerts at 14.4× (fast) and 6× (slow)
