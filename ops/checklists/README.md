# Operational Checklists for Express T2S Platform

Operational checklists are a critical component of our DevOps strategy, ensuring **consistency**, **auditability**, and **risk reduction** across all deployment and maintenance activities for the Express T2S platform. They formalize the process of managing the Internal Developer Platform (IDP) and associated microservices.

## Available Checklists

| Checklist File | Purpose | Key Focus |
| :--- | :--- | :--- |
| [pre_deployment.md](./pre_deployment.md) | Standardize all steps required before a new release or update is initiated. | Pre-flight health checks, dependency verification, security scanning. |
| [post_deployment.md](./post_deployment.md) | Verify the health, connectivity, and functionality of all services immediately after a release. | Smoke testing, service mesh registration, alerting confirmation. |
| [soc2_controls_checklist.md](./soc2_controls_checklist.md) | Document and audit the continuous adherence to SOC 2 compliance requirements. | Access control, change management, system monitoring. |

## Usage

These documents should be utilized by all DevOps and SRE personnel prior to and following any changes to the production environment. They serve as a single source of truth for critical operational procedures.
