# Post-Deployment Checklist for NRP Platform

- [ ] **GitOps Status:** Deployment completed successfully via ArgoCD/Flux and reconciliation is healthy.
- [ ] **Infrastructure:** All sub-chart dependencies (e.g., PostgreSQL) are stable and healthy.
- [ ] **App Config:** New ConfigMap (app-config.yaml) successfully mounted and accessible by Backstage container.
- [ ] **Ingress/Connectivity:** Application is accessible via Ingress (`backstage.nrp-platform.com`) and TLS certificate is valid.
- [ ] **Health Probes:** Backstage Deployment Liveness and Readiness probes are passing consistently.
- [ ] **Backstage Catalog:** Catalog Processor successfully ingested all entities and no errors are present on the Catalog page.
- [ ] **SLOs/Telemetry:** No immediate increase in error rate or latency beyond defined SLO thresholds.
- [ ] **Monitoring:** Logs and traces confirm normal service behavior; synthetic checks are passing.
- [ ] **Alerting:** No abnormal alerts or warnings in the first 30–60 minutes.
- [ ] **Documentation:** Observability dashboards and runbooks are updated (if needed).
- [ ] **Handover:** Relevant ticket/issue is updated with deployment outcome and metrics summary.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
