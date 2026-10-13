# Disaster Recovery Runbooks for Golden Platform

Disaster Recovery (DR) strategies are essential for maintaining the **availability** and **integrity** of the Golden Platform microservices and the underlying Internal Developer Platform (IDP) (Backstage). This folder contains cloud-specific runbooks detailing the procedures required to restore service following a catastrophic event.

Our DR approach is focused on protecting the **stateful data** (primarily PostgreSQL) and quickly re-establishing service connectivity through GitOps pipelines.

## Scope

This directory contains cloud-specific DR runbooks for major providers:

* [aws_dr_runbook.md](./aws_dr_runbook.md)
* [azure_dr_runbook.md](./azure_dr_runbook.md)
* [gcp_dr_runbook.md](./gcp_dr_runbook.md)
* [oci_dr_runbook.md](./oci_dr_runbook.md)

## Runbook Outline

Each cloud-specific runbook outlines the following critical areas tailored to the Golden Platform environment:

1. **RPO / RTO Targets:** Defines acceptable data loss and service restoration time for microservices and IDP.
2. **Backup Strategy:** Details the mechanism for backing up critical data, particularly the Backstage PostgreSQL instance.
3. **Restore & Failover:** Step-by-step procedures for restoring stateful data and executing service failover to the DR region.
4. **Validation & Cutback:** Procedures for validating service functionality post-restore and returning traffic to the primary region.

---

*Copyright (c) 2026 Rev. Dr. Emmanuel Naweji. All rights reserved.*
