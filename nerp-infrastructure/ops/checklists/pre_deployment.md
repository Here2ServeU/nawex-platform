# Pre-Deployment Checklist for NRP Platform

- [ ] **Change Approval:** Change request / ticket approved by required stakeholders.
- [ ] **Code Readiness:** Code merged to main branch and meets code standards.
- [ ] **CI Pipeline:** CI pipeline green (all unit/integration tests, linting, security scans passed).
- [ ] **Image Security:** Image scanned (Trivy/Snyk) and pushed to container registry; no critical vulnerabilities found.
- [ ] **Helm Integrity:** Helm chart version bumped and committed; `helm lint` and `helm template --dry-run` are successful.
- [ ] **Config Validation:** New configuration in `values.yaml` reviewed and validated against environment-specific secrets.
- [ ] **Infrastructure Capacity:** Kubernetes cluster quota and node capacity verified (resource limits available).
- [ ] **Secret Management:** New/rotated secrets (e.g., PostgreSQL credentials) verified in Secret Manager.
- [ ] **SLO Impact:** SLO impact reviewed; error budget available for potential deployment issues.
- [ ] **Runbooks:** Runbooks updated if new failure modes or service dependencies were introduced.
- [ ] **Rollback Plan:** Rollback plan clearly documented and tested (revert to previous stable tag).

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
