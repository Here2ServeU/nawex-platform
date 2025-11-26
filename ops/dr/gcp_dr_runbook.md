# GCP Disaster Recovery Runbook

## Scope
- GKE clusters
- Cloud SQL / Firestore
- GCS buckets
- Artifact Registry

## Strategy
- Multi-region or dual-region GCS for critical data.
- Cross-region replicas for Cloud SQL.
- Terraform-managed GKE clusters per region.

## Steps

1. **Confirm Outage**
   - Validate issue is regional and not local.

2. **Promote Replica**
   - Promote standby Cloud SQL instance if applicable.

3. **Create/Scale GKE in DR Region**
   - Apply Terraform DR workspace configs.

4. **Reconcile via GitOps**
   - Point GitOps controllers at DR GKE cluster.
   - Deploy all apps and platform services.

5. **Switch Traffic**
   - Update Cloud DNS / load balancers to target DR.
   - Confirm traffic flows correctly.

6. **Post-Event**
   - Review DR performance.
   - Adjust RPO/RTO targets if needed.
