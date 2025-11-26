# Azure Disaster Recovery Runbook

## Scope
- AKS clusters
- Azure SQL / Cosmos DB
- Azure Storage
- Container Registry (ACR)

## DR Strategy
- Use paired regions (e.g., East US / West US).
- Geo-redundant storage for blobs and state.
- Active geo-replication for databases.
- ACR replication for container images.

## Steps

1. **Assess Impact**
   - Verify that primary region is unavailable / severely degraded.

2. **Failover Databases**
   - Promote secondary replicas to primary.

3. **Deploy AKS in DR Region**
   - Apply Terraform with DR-specific variables.
   - Ensure node pools, networking, and ingress are in place.

4. **Re-point GitOps**
   - Configure ArgoCD/Flux to target DR AKS cluster.
   - Reconcile platform and app Helm charts.

5. **Switch Traffic**
   - Update Azure Front Door / Traffic Manager / DNS to target DR endpoints.

6. **Validation**
   - Run synthetic checks and end-to-end tests.
   - Monitor SLOs for at least 1–2 hours.
