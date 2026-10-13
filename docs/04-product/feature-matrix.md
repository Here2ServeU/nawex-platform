# Feature Matrix

| Capability | Healthcare | Fintech | AI Infra (GPU) | Modernization |
|---|:-:|:-:|:-:|:-:|
| Platform API (`/v1/fraud/score`, `/v1/decisions`, `/v1/roi/{vertical}`) | ✓ | ✓ | ✓ | ✓ |
| LSTM/TCN reliability prediction | ✓ | ✓ | ✓ | — |
| Domain anomaly detection | PHI access, vitals | Fraud, payment failures | Thermal, memory, ECC/XID, idle | Assessment blockers & risk |
| Autonomous remediation (governed) | ✓ | ✓ | ✓ | Approval-only (critical) |
| AI-safety controls (guardrails, budgets, approvals, kill switch, audit) | ✓ | ✓ | ✓ | ✓ |
| PHI / PII redaction | ✓ | ✓ | — | ✓ (inventory metadata) |
| ROI calculator (`golden roi`) | ✓ | ✓ | ✓ | — |
| Grafana dashboards | golden-healthcare | golden-fintech | golden-gpu | golden-migration |
| Compliance mappings | HIPAA, HDS | PCI DSS, SOX, PSD2, GLBA | FinOps, EU AI Act, NIST AI RMF | SOC 2 change mgmt |
| GPU-accelerated training (AMP/TF32/compile) | ✓ | ✓ | ✓ | — |
| OpenShift Virtualization + MTV assets | — | — | — | ✓ |
| Common to all | One image · Helm/GitOps · Prometheus/Grafana/Loki/Tempo · API-key auth · rate limiting | | | |
