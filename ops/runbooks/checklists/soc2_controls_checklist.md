# SOC 2 Controls Checklist (Deployment Focus)

- [ ] **Change Management:** All changes traceable to an approved ticket or work item.
- [ ] **Code Review:** At least one peer review before merge, ensuring security and adherence to standards.
- [ ] **Version Control:** Git history preserved (no force pushes to main/production branches).
- [ ] **Configuration:** All application/infrastructure configuration (e.g., Helm values) stored in Git.
- [ ] **Secrets Management:** Secrets are stored securely (Vault, AWS Secrets Manager, etc.) and NOT in Git.
- [ ] **CI Pipeline Checks:** CI pipeline includes:
    - [ ] Static code analysis
    - [ ] Dependency vulnerability scan
    - [ ] Container image scan
- [ ] **Deployment Tooling:** GitOps tool logs (ArgoCD/Flux) retained for the required audit period.
- [ ] **Production Access:** Access to production cluster restricted to GitOps service accounts + break-glass process.
- [ ] **DB Access Control:** Direct access to production database (PostgreSQL) is restricted and auditable.
- [ ] **Monitoring & Alerting:** Comprehensive monitoring and alerting is configured for all critical services.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
