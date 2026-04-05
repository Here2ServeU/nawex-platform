# nerp-core

Platform orchestration hub for the Naweji Enterprise Reliability Platform.
Contains the consulting demo runner, PhD research documentation, shared
orchestration scripts, observability configuration, and the full Docker
Compose stack for local development.

---

## Quick Start

### Run the Consulting Demo

```bash
# From the monorepo root
python nerp-core/demo_client.py --vertical hospital --client "City Medical Center"
python nerp-core/demo_client.py --vertical bank     --client "National Finance Corp"
```

### Launch the Full Platform Stack

```bash
cd nerp-core
docker compose up -d
```

Services started:

| Service | URL | Purpose |
| ------- | --- | ------- |
| nerp-client-portal | <http://localhost:3001> | Executive demo dashboard |
| Grafana | <http://localhost:3000> | Observability |
| Prometheus | <http://localhost:9090> | Metrics |
| Healthcare (EHR / Clinical / Gateway) | ports 8093–8095 | Healthcare microservices |
| Fintech (Transactions / Fraud / Gateway) | ports 8090–8092 | Fintech microservices |
| Kafka | port 9092 | Event backbone |
| Redis (fintech / healthcare) | ports 6380–6381 | Cache |

---

## Directory Structure

```text
nerp-core/
├── demo_client.py              # Single-command consulting demo runner
├── demo_report_template.html   # Jinja2 HTML leave-behind client report
├── docker-compose.yaml         # Full platform stack (all services)
│
├── research/
│   └── methodology/            # PhD research methodology documentation
│       ├── lstm_sli_methodology.md
│       ├── fraud_detection_methodology.md
│       ├── phi_anomaly_methodology.md
│       └── clinical_safety_methodology.md
│
├── docs/
│   ├── consulting/             # Consulting playbook and sales materials
│   ├── 01-executive/           # Investor and executive narrative docs
│   ├── architecture/           # System architecture documentation
│   ├── compliance/             # HIPAA, PCI-DSS, SOC2, SOX mapping docs
│   ├── product/                # Platform capabilities and edition guides
│   ├── 05-operations/          # Runbooks and operational guides
│   ├── 06-demos/               # Demo scripts and runbooks
│   └── guides/                 # Developer and operator guides
│
├── datasets/                   # Reference CSV datasets (SLI, fintech, healthcare)
├── robotics/                   # gRPC surgical robot prototype (edge AI)
├── tests/                      # Integration, unit, security, performance tests
├── tools/                      # HTTP client files, k6 load tests, Kafka tools
├── compliance/                 # Audit log and evidence scaffolding
├── assets/                     # Platform branding and presentation assets
├── verticals/                  # Vertical-specific orchestration stubs
├── data_platform/              # Data pipeline scaffolding
├── platform/                   # Platform services scaffolding
└── experiments/                # Research experiment scaffolding
```

---

## Demo Runner Reference

`demo_client.py` orchestrates a 6-act narrated demo (~3 minutes):

| Act | Duration | What It Shows |
| --- | -------- | ------------- |
| 1 — Platform Overview | ~20s | NERP positioning and AI capabilities |
| 2 — Data Ingestion | ~30s | Synthetic patient vitals / transaction stream |
| 3 — AI Detection | ~40s | Real `detect_fraud` / `detect_phi_anomalies` scoring |
| 4 — Explainability | ~20s | Feature contributions in plain English |
| 5 — Business Value | ~30s | Dollar impact via Bayesian expected-value methodology |
| 6 — ROI Summary | ~20s | Contract justification + HTML report |

Output: HTML client report saved to `./demo_output/<client>/`

---

## Research Methodology

All four PhD methodology documents in `research/methodology/` cite the actual
model weights and thresholds in the code, written for specific client audiences:

| Document | Audience | Regulatory Frame |
| -------- | -------- | ---------------- |
| `lstm_sli_methodology.md` | Bank CTO / Hospital CIO | SRE / IEEE standards |
| `fraud_detection_methodology.md` | Bank Risk Officer | BSA/AML, PCI-DSS |
| `phi_anomaly_methodology.md` | Hospital Compliance Officer | HIPAA §164.312(b) |
| `clinical_safety_methodology.md` | CMIO / Patient Safety Officer | NEWS2, Sepsis-3 |

---

## Makefile Targets

```bash
make bootstrap       # Install all dependencies across subprojects
make platform-start  # docker compose up -d
make health          # Health check all services
make demo            # Run the hospital consulting demo
make demo-bank       # Run the financial services consulting demo
make test            # Run all tests
make clean           # Stop and remove containers
```

---

## Docker Compose Networking

The `nerp-client-portal` service joins all three networks (`clinical-net`,
`fintech-net`, `healthcare-net`) so the executive dashboard can represent
both the healthcare and financial services verticals from a single portal.
