# /ops — SRE & Platform Governance for NRP

This directory contains the central source of truth for **Site Reliability Engineering (SRE)** practices, **operational documentation**, and **platform governance** used to support the **NRP Microservices** and the **Backstage Internal Developer Platform (IDP)**. All procedures adhere to a GitOps-first, audit-ready framework.

## Key Operational Areas

* **Checklists (`checklists/`):** Standardized checklists for pre/post-deployment validation and **SOC 2** compliance auditing.
* **Disaster Recovery (`dr/`):** Multi-cloud **DR Runbooks** focusing on failover for core services and **PostgreSQL** persistence.
* **On-Call (`on-call/`):** Policies and escalation paths refined for platform-specific severity levels and response times.
* **Playbooks (`playbooks/`):** Tactical guides for complex procedures like DB failover, Kafka draining, and **GitOps rollback**.
* **RBAC (`rbac/`):** **Kubernetes RBAC** templates defining least-privilege access for SREs, developers, and observers.
* **Scripts (`scripts/`):** Utility automation scripts for maintenance and monitoring tasks.
* **SRE (`sre/`):** General SRE principles, SLO/SLI definitions, and team structure documentation.
* **Terraform (`terraform/`):** Infrastructure-as-Code definitions for platform components (e.g., EKS/AKS/GKE clusters).

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
