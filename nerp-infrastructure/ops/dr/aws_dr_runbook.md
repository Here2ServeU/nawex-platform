# AWS Disaster Recovery Runbook for NRP Platform

## Scope
Covers critical components of the NRP microservices platform:
* EKS clusters (for all microservices and Backstage IDP)
* **Backstage PostgreSQL RDS** / DynamoDB
* S3 buckets (for state and assets)
* ECR registries

## RPO / RTO
* RPO: 15 minutes (via automated backups and cross-region replication).
* RTO: 1–2 hours for full region failover of all microservices.

## Key Mechanisms
* Infrastructure as Code: EKS cluster and supporting services defined via **Terraform** (multi-region capable).
* Database: **Backstage PostgreSQL** configured with cross-region read replicas and automated backups.
* Storage: S3 versioning + cross-region replication for state and assets.
* Image Management: ECR image replication to secondary region.
* Deployment: Application deployment managed via **GitOps** (ArgoCD/Flux).

## Steps (Region Failover)
1. **Declare Disaster**
    * Confirm region-wide impact (not a localized issue).
    * Activate communications plan.
2. **Promote Backstage Database**
    * Promote the cross-region PostgreSQL replica (for Backstage) to primary.
    * Update connection secrets/credentials in AWS Secrets Manager (if needed).
3. **Provision Infra in DR Region**
    * Run Terraform against DR workspace/vars to create: EKS cluster, Networking, Load balancers, Supporting services.
4. **Restore State**
    * Restore any missing S3 state or configurations if required.
5. **Deploy Applications via GitOps**
    * Point ArgoCD/Flux to the new EKS cluster/context.
    * **Reconcile all applications from Git**, ensuring the Backstage chart and microservices deploy successfully.
6. **Validate & Cutover**
    * Execute smoke tests, SLO checks, and Post-Deployment Checklist.
    * Switch DNS (Route 53) to the DR load balancer endpoints.
7. **Post-Event**
    * Document incident and DR effectiveness.
    * Plan failback when the primary region is healthy.

---

*Copyright (c) 2026 Naweji Enterprise Reliability Platform (NERP). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
