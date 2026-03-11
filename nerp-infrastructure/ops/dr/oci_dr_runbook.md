# OCI Disaster Recovery Runbook for NRP Platform

## Scope
Covers critical components of the NRP microservices platform:
* OKE (Oracle Kubernetes Engine) clusters (for all microservices and Backstage IDP)
* Autonomous DB / DB Systems (for **Backstage PostgreSQL persistence**)
* Object Storage (for state and assets)
* OCI Container Registry (OCIR)

## RPO / RTO
* RPO: 15 minutes (via automated backups and cross-region replication).
* RTO: 1–2 hours for full region failover of all microservices.

## Strategy
* Infrastructure as Code: OKE cluster and networking managed via **Terraform** (multi-region capable).
* Database: **Backstage PostgreSQL** data protected via cross-region replication or Autonomous DB failover mechanisms.
* Storage: Cross-region replication policies for Object Storage.
* Image Management: OCIR replication policies to secondary region.
* Deployment: Application restoration managed entirely via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1. **Identify Disaster Event**
    * Confirm primary region outage and activate communications plan.
2. **Database Recovery**
    * Restore Backstage DB from backups or activate standby/replica in the DR region.
    * Update connection secrets/credentials in OCI Vault (if needed).
3. **Provision OKE in DR Region**
    * Run Terraform against DR variables to stand up the OKE cluster, networking, and load balancers.
4. **GitOps Deploy**
    * Configure ArgoCD/Flux to use DR OKE context.
    * **Redeploy all Helm charts from Git**, ensuring the Backstage chart and microservices deploy successfully.
5. **DNS / Traffic Cutover**
    * Update DNS and any global load balancers to point to DR endpoints.
    * Validate connectivity and execute Post-Deployment Checklist.
6. **Monitor & Validate**
    * Monitor SLOs and error budgets; ensure systems are stable.
7. **Failback Planning**
    * Once primary region is stable, plan migration back with minimal downtime.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
