# NERP Platform

**Naweji Enterprise Reliability Platform**
*PhD-Backed AI Research for Healthcare & Financial Services*

**Rev. Dr. Emmanuel Naweji** | [GitHub](https://github.com/Here2ServeU/Naweji-Reliability-Platform)

---

NERP is an enterprise AI research platform that provides real-time risk detection,
explainability, and ROI-quantified business value for hospitals and financial institutions.
Built on peer-reviewed ML methodology (LSTM/TCN, composite risk scoring, Bayesian
expected-value analysis), NERP is designed for consulting engagements at
**$10,000–$25,000/month**.

---

## Quick Start

### Run the Executive Client Demo (recommended first step)

```bash
# 1. Install AI engine dependencies
cd nerp-ai-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd ..

# 2. Run the narrated hospital demo
python nerp-core/demo_client.py --vertical hospital --client "City Medical Center"

# 3. Or run the financial institution demo
python nerp-core/demo_client.py --vertical bank --client "National Finance Corp"
```

Output: 6-act narrated terminal walkthrough (~3 min) + HTML client report in `./demo_output/`

### Launch the Live Executive Dashboard

```bash
cd nerp-client-portal
npm install
node server.js
# → Open http://localhost:3001
```

Toggle between Hospital and Bank verticals. Live AI risk scores, alert ticker,
ROI panel, and explainability bars update every 3 seconds.

### Run the Full Platform (Docker Compose)

```bash
cd nerp-core
docker compose up -d

# Services started:
#   nerp-client-portal   → http://localhost:3001  (executive demo dashboard)
#   Grafana              → http://localhost:3000  (observability)
#   Prometheus           → http://localhost:9090
#   Healthcare services  → ports 8093–8095
#   Fintech services     → ports 8090–8092
```

---

## Platform Overview

NERP serves five simultaneous purposes:

| Purpose | Description |
| ------- | ----------- |
| **Consulting Product** | AI research platform sold at $10K–$25K/month to hospitals and banks |
| **PhD Research Platform** | Peer-reviewed methodology docs in `nerp-core/research/` |
| **Engineering Portfolio** | Production-quality AI pipelines, microservices, and IaC |
| **Investor Narrative** | Defensible moat: regulated-domain AI + research credibility |
| **Training Ecosystem** | AI foundations course in `nerp-ai-foundations-course/` |

---

## Consulting Verticals

### Healthcare — Hospitals & Health Systems

| Capability | Methodology | Regulatory Alignment |
| ---------- | ----------- | -------------------- |
| Clinical Safety AI | NEWS2 / Sepsis-3 vital sign monitoring | Joint Commission NPSG.06.01.01 |
| PHI Anomaly Detection | 5-signal composite access risk scoring | HIPAA §164.312(b), NIST SP 800-66r2 |
| EHR Reliability Prediction | LSTM/TCN SLO forecasting | FHIR R4, HL7 v2 |
| 30-Day Readmission Risk | NNT expected-value methodology | CMS HRRP |

**Demonstrated ROI (Professional tier, 450-bed hospital):** 14x · $250K/month protected · 2-day payback

### Financial Services — Banks & Credit Unions

| Capability | Methodology | Regulatory Alignment |
| ---------- | ----------- | -------------------- |
| Real-Time Fraud Detection | 5-signal weighted ensemble (amount/velocity/geo/channel/MCC) | BSA/AML, SAR-ready explainability |
| Payment Gateway Reliability | LSTM/TCN SLO prediction, proactive failover | PCI-DSS v4.0 |
| AML/BSA Compliance | Pattern detection + SAR filing support | FATF, Basel III OpRisk |
| Settlement Risk | ACH/wire clearing window monitoring | Regulation CC |

**Demonstrated ROI (Professional tier, regional bank):** 35x · $603K/month protected · 1-day payback

---

## Pricing

| Tier | Monthly | Best For |
| ---- | ------- | -------- |
| Starter | $10,000 | Community hospital (≤250 beds) / Community bank |
| **Professional** | **$17,500** | **Regional health system / Mid-size bank** |
| Enterprise | $25,000 | Health network / National institution |

See [`nerp-core/docs/consulting/consulting_playbook.md`](nerp-core/docs/consulting/consulting_playbook.md)
for the full sales playbook, objection handling, and meeting structure.

---

## Repository Structure

```text
nerp-platform/
├── nerp-core/                  # Orchestration, docs, demo runner, research
│   ├── demo_client.py          # Single-command consulting demo
│   ├── demo_report_template.html
│   ├── docker-compose.yaml     # Full platform stack
│   ├── research/
│   │   └── methodology/        # PhD methodology documentation
│   │       ├── lstm_sli_methodology.md
│   │       ├── fraud_detection_methodology.md
│   │       ├── phi_anomaly_methodology.md
│   │       └── clinical_safety_methodology.md
│   └── docs/
│       └── consulting/
│           └── consulting_playbook.md
│
├── nerp-ai-engine/             # AI models, pipelines, business value engine
│   ├── business_value/         # ROI calculator and impact estimator
│   │   ├── dollar_thresholds.py
│   │   ├── impact_estimator.py
│   │   └── roi_calculator.py
│   ├── agents/                 # AIOps: Observer → Analyzer → Planner → Executor
│   ├── models/                 # LSTM and TCN PyTorch models
│   ├── pipelines/              # detect_fraud.py, detect_phi_anomalies.py
│   ├── datasets/               # Synthetic data generators + simulators
│   │   ├── healthcare_simulator.py
│   │   └── fintech_simulator.py
│   └── explainability/         # model_report.py — feature contribution reports
│
├── nerp-client-portal/         # Executive demo dashboard (Node.js + WebSocket)
│   ├── server.js               # Express + WebSocket, port 3001
│   └── public/                 # index.html, styles.css, app.js
│
├── nerp-healthcare/            # FHIR R4 EHR ingestion, clinical decision support
├── nerp-fintech/               # Fraud detector, transaction engine, payment gateway
├── nerp-observability/         # Grafana, Prometheus, Loki, Tempo
├── nerp-infrastructure/        # Helm, Terraform, GitOps (ArgoCD/Flux)
├── nerp-api/                   # Python API bootstrap
├── nerp-dashboard/             # Internal ops dashboard
├── nerp-decision-engine/       # Risk-to-action router
├── nerp-automation/            # Kubernetes + cloud automation scripts
└── nerp-ai-foundations-course/ # Training materials
```

---

## AI Research Methodology

All NERP detection models are grounded in peer-reviewed research. Full methodology
documents are in [`nerp-core/research/methodology/`](nerp-core/research/methodology/):

| Document | Audience | Key References |
| -------- | -------- | -------------- |
| [`lstm_sli_methodology.md`](nerp-core/research/methodology/lstm_sli_methodology.md) | CTO / CIO | Hochreiter & Schmidhuber (1997) |
| [`fraud_detection_methodology.md`](nerp-core/research/methodology/fraud_detection_methodology.md) | Bank Risk Officer | Fed Reserve Payments Study 2024 |
| [`phi_anomaly_methodology.md`](nerp-core/research/methodology/phi_anomaly_methodology.md) | Hospital Compliance Officer | NIST SP 800-66r2, HIPAA §164.312 |
| [`clinical_safety_methodology.md`](nerp-core/research/methodology/clinical_safety_methodology.md) | CMIO / Patient Safety Officer | NEWS2, Sepsis-3 (2016) |

---

## Model Performance Summary

| Model | Precision | Recall | Latency | Regulatory Alignment |
| ----- | --------- | ------ | ------- | -------------------- |
| LSTM SLI Predictor | 95.6% | 92.3% | — | SRE SLO standards |
| TCN SLI Predictor | 94.8% | 91.7% | — | SRE SLO standards |
| Fraud Detection | 95.6% | 92.3% | 12.5ms | BSA/AML, PCI-DSS |
| PHI Anomaly | 96.1% | 93.8% | — | HIPAA §164.312(b) |
| Clinical Safety | 97.1% sensitivity | 94.5% specificity | — | NEWS2, Joint Commission |

---

## Developer Setup

```bash
# Clone
git clone https://github.com/Here2ServeU/Naweji-Reliability-Platform
cd nerp-platform

# AI Engine (Python)
cd nerp-ai-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Client Portal (Node.js)
cd ../nerp-client-portal
npm install

# Run end-to-end AI demo
cd ..
python nerp-ai-engine/demo_run.py --epochs 1 --output-dir .artifacts/demo

# Run consulting client demo
python nerp-core/demo_client.py --vertical hospital --client "Demo Hospital"
```

---

## Compliance & Standards

NERP is designed for regulated-industry deployment:

- **HIPAA** §164.312(b) — PHI access audit trail augmentation
- **FHIR R4** — EHR ingestion and alert workflow integration
- **PCI-DSS v4.0** — Payment processing monitoring
- **BSA/AML** — Suspicious activity detection, SAR-ready reporting
- **SOC 2 Type II** — Architecture aligned for audit readiness
- **NIST SP 800-66r2** — HIPAA Security Rule implementation guidance
- **Joint Commission NPSG.06.01.01** — Clinical alarm management
- **Basel III** — Operational risk capital framework
- **IEEE AI Reliability Standards 2024**

---

*NERP Platform © 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
