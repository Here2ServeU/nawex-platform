# GCP Disaster Recovery Runbook for NRP Platform

## Scope
Covers critical components of the NRP microservices platform:
* **GKE clusters** (for all microservices and **Backstage IDP**)
* **Cloud SQL** (for Backstage PostgreSQL persistence) / Firestore
* **GCS buckets** (for state and assets)
* **Artifact Registry** (for container images)

## RPO / RTO
* RPO: 15 minutes (via automated backups and cross-region replication).
* RTO: 1–2 hours for full region failover of all microservices and the IDP.

## Strategy
* Infrastructure as Code: GKE clusters and networking managed via **Terraform** (multi-region capable).
* Database: **Cloud SQL for PostgreSQL** configured with cross-region replicas for minimal data loss.
* Storage: Multi-region or dual-region GCS for critical data and persistent volumes.
* Deployment: Application restoration managed entirely via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1. **Confirm Outage**
    * Validate issue is regional and not local.
    * Activate incident communications plan.
2. **Promote Backstage Database**
    * Promote the cross-region Cloud SQL PostgreSQL replica to primary.
    * Update connection secrets/credentials in Secret Manager (if needed).
3. **Create/Scale GKE in DR Region**
    * Apply Terraform DR workspace configs to provision the GKE cluster, Load Balancers, and necessary networking.
4. **Reconcile via GitOps**
    * Point GitOps controllers (ArgoCD/Flux) at DR GKE cluster context.
    * **Deploy all apps and platform services from Git**, ensuring the Backstage chart starts successfully.
5. **Switch Traffic**
    * Update **Cloud DNS** / load balancers to target the DR Ingress/Endpoints.
    * Confirm traffic flows correctly and smoke tests pass.
6. **Post-Event**
    * Review DR performance and document lessons learned.
    * Plan the failback process when the primary region is restored.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
