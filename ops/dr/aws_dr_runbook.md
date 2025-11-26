# AWS Disaster Recovery Runbook

## Scope
Covers:
- EKS clusters
- RDS / DynamoDB
- S3 buckets
- ECR registries

## RPO / RTO
- RPO: 15 minutes (via automated backups and cross-region replication).
- RTO: 1–2 hours for full region failover.

## Key Mechanisms
- EKS cluster defined via Terraform (multi-region capable).
- RDS with cross-region read replicas and automated backups.
- S3 versioning + cross-region replication for state and assets.
- ECR image replication to secondary region.

## Steps (Region Failover)

1. **Declare Disaster**
   - Confirm region-wide impact (not a localized issue).

2. **Promote Secondary DB**
   - Promote cross-region replica to primary.

3. **Provision Infra in DR Region**
   - Run Terraform against DR workspace/vars to create:
     - EKS cluster
     - Networking
     - Load balancers
     - Supporting services

4. **Restore State**
   - Restore any missing S3 state or configs if required.

5. **Deploy via GitOps**
   - Point ArgoCD/Flux to the new cluster/context.
   - Reconcile all apps from Git.

6. **Validate & Cutover**
   - Smoke tests + SLO checks.
   - Switch DNS (Route 53) to DR load balancer endpoints.

7. **Post-Event**
   - Document incident and DR effectiveness.
   - Plan failback when primary region is healthy.
