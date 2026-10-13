# 07: SOX Compliance & Financial Controls Mapping

> **Mapping, not certification.** This document maps platform controls to the SOX Sections 302/404 (ITGC). The platform has not been audited or certified against it. Rows describe the target control design; only items that link to code or config in this repository are implemented here, and the rest are requirements for the deploying organisation. See [CLAIMS.md](../CLAIMS.md).

## Executive Summary

This document maps the **Golden Platform** controls to the **Sarbanes-Oxley Act (SOX)** requirements, specifically Sections 302 and 404 governing internal controls over financial reporting (ICFR). The platform ensures the integrity, availability, and auditability of financial data processing systems that feed into corporate reporting and regulatory filings.

## SOX Section 404: Internal Controls Mapping

| SOX Control Objective | Platform Control Implementation | Evidence Location |
| --- | --- | --- |
| **Change Management** | All infrastructure changes are version-controlled via [GitOps](/deploy/gitops) (ArgoCD/Flux); no manual production changes permitted. Every change has a commit SHA, author, and approval trail. | [`/gitops`](/deploy/gitops) |
| **Access Controls** | Role-Based Access Control (RBAC) with SCIM provisioning, SSO enforcement, and MFA for all privileged access to financial processing systems. | [`/sre/security`](/ops/sre/security) |
| **Segregation of Duties** | Kubernetes namespaces enforce logical separation between development, staging, and production environments. RBAC policies prevent developers from accessing production financial data. | [`/terraform`](/deploy/terraform), [`/sre/security/reliability-rbac-model.md`](/ops/sre/security/reliability-rbac-model.md) |
| **Data Integrity** | Cryptographic hashing of all financial transaction records; immutable audit logs with WORM protection prevent post-hoc modification. | [`/docs/compliance/03-audit-logging-policy.md`](/docs/compliance/03-audit-logging-policy.md) |
| **System Availability** | 99.9% API availability SLO objective ([`slo_rules.yml`](/observability/prometheus/rules/slo_rules.yml)); [Active-Active Multi-Cloud](/docs/architecture/05-active-active-resilience.md) with < 30 s RTO is a design target, not measured. | [`/docs/architecture/05-active-active-resilience.md`](/docs/architecture/05-active-active-resilience.md) |
| **Monitoring & Alerting** | Continuous monitoring via OTel, Prometheus, and Datadog with AI-driven anomaly detection for unauthorized access patterns. | [`/sre/observability`](/ops/sre/observability) |
| **Backup & Recovery** | Multi-region backup design with a near-zero RPO target; DR procedures to be tested quarterly with the chaos scripts (no drill results yet). | [`/docs/compliance/04-disaster-recovery-plan.md`](/docs/compliance/04-disaster-recovery-plan.md) |

## SOX Section 302: CEO/CFO Certification Support

The platform provides automated evidence collection for executive certification:

* **Financial Data Pipeline Integrity**: Every transformation applied to financial data (ETL, aggregation, reporting) is logged with input/output checksums, enabling full reproducibility of any reported figure.
* **Automated Control Testing**: The [AI Brain](/src/golden/ai/) continuously validates that ICFR controls are functioning—detecting drift in access patterns, configuration changes, or unusual data flows that could indicate control failures.
* **Evidence Repository** *(deployment requirement)*: Compliance evidence (access logs, change records, test results) should be archived in encrypted, immutable storage for 7+ years per SOX retention requirements.

## IT General Controls (ITGC) Framework

| ITGC Domain | Implementation Detail |
| --- | --- |
| **Program Development** | CI/CD pipelines with mandatory code review, SAST/DAST scanning, and approval gates before production deployment. |
| **Program Changes** | GitOps-enforced immutable deployments; rollback capability via Git revert with full audit trail. |
| **Computer Operations** | Automated runbooks in [`/ops/playbooks`](/ops/runbooks/playbooks); incident response procedures with defined escalation paths. |
| **Access to Programs & Data** | OIDC-based authentication, SCIM lifecycle management, quarterly access reviews with automated deprovisioning. |

## Continuous SOX Compliance Monitoring

The [Predictive Reliability Framework](/docs/architecture/04-predictive-reliability-framework.md) enables proactive SOX compliance:

* **Control Effectiveness Monitoring**: ML models analyze control execution patterns to predict control failures before they result in material weaknesses.
* **Anomaly-Based Fraud Detection**: The AI engine monitors financial transaction patterns for statistical anomalies that could indicate fraudulent activity or unauthorized data manipulation.
* **Automated Reporting** *(design)*: Quarterly SOX evidence packs generated from platform telemetry, aimed at reducing manual audit preparation effort (no measured reduction).

---

### Audit Readiness

This mapping is intended to help the operating organisation provide evidence to external auditors that IT controls supporting financial reporting are designed and operating effectively. Operating effectiveness can only be shown by the organisation over a real reporting period.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
