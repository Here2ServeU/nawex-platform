# Azure Disaster Recovery Runbook for Express T2S Platform

## Scope
Covers critical components of the Express T2S microservices platform:
* AKS clusters (for all microservices and Backstage IDP)
* **Azure PostgreSQL** / Azure SQL / Cosmos DB
* Azure Storage (for state and assets)
* Container Registry (ACR)

## RPO / RTO
* RPO: 15 minutes (via automated backups and cross-region replication).
* RTO: 1–2 hours for full region failover of all microservices.

## DR Strategy
* Infrastructure as Code: AKS cluster and supporting services defined via **Terraform** or Bicep (multi-region capable).
* Database: **Backstage PostgreSQL** configured with active geo-replication or cross-region backups.
* Storage: Geo-redundant storage (GRS) for state and assets.
* Image Management: ACR geo-replication to secondary region.
* Deployment: Application deployment managed via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1.  **Assess Impact**
    * Verify that primary region is unavailable / severely degraded.
    * Activate communications plan.
2.  **Failover Backstage Database**
    * Promote the geo-replicated database replica (for Backstage) to primary.
    * Update connection secrets/credentials in Azure Key Vault (if needed).
3.  **Deploy AKS in DR Region**
    * Apply Terraform/Bicep with DR-specific variables to deploy the new AKS cluster, networking, and ingress.
4.  **Restore State**
    * Restore any missing Azure Storage state or configurations if required.
5.  **Re-point GitOps & Deploy Applications**
    * Configure ArgoCD/Flux to target DR AKS cluster.
    * **Reconcile all applications from Git**, ensuring the Backstage chart and microservices deploy successfully.
6.  **Switch Traffic & Validation**
    * Update Azure Front Door / Traffic Manager / DNS to target DR endpoints.
    * Execute synthetic checks, SLO checks, and Post-Deployment Checklist.
7.  **Post-Event**
    * Document incident and DR effectiveness.
    * Plan failback when the primary region is healthy.
