# ops/runbooks — Operational Runbooks & Platform Governance

This directory contains the central source of truth for **Site Reliability Engineering (SRE)** practices, **operational documentation**, and **platform governance** used to support the **Golden Platform Microservices** and the **Backstage Internal Developer Platform (IDP)**. All procedures adhere to a GitOps-first, audit-ready framework.

## Key Operational Areas

* **Checklists (`checklists/`):** Standardized checklists for pre/post-deployment validation and **SOC 2** compliance auditing.
* **Disaster Recovery (`dr/`):** Multi-cloud **DR Runbooks** focusing on failover for core services and **PostgreSQL** persistence.
* **Migration (`migration/`):** Cutover and rollback runbooks for VMware → OpenShift Virtualization waves (MTV).
* **On-Call (`on-call/`):** Policies and escalation paths refined for platform-specific severity levels and response times.
* **Playbooks (`playbooks/`):** Tactical guides for complex procedures like DB failover, Kafka draining, and **GitOps rollback**.
* **RBAC (`rbac/`):** **Kubernetes RBAC** templates defining least-privilege access for SREs, developers, and observers.
* **SRE (`../sre/`):** SRE principles, SLO/SLI definitions, chaos experiments, AIOps tooling.
* **Infrastructure-as-Code** lives in `deploy/terraform/`; legacy helper scripts in `scripts/tools/`.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
