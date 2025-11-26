# OCI Disaster Recovery Runbook

## Scope
- OKE (Oracle Kubernetes Engine)
- Autonomous DB / DB Systems
- Object Storage
- OCI Container Registry (OCIR)

## Strategy
- Use multiple OCI regions with:
  - Replication policies for Object Storage.
  - Cross-region DB backups / replication.
  - Terraform modules for OKE in primary and DR regions.

## Steps

1. **Identify Disaster Event**
   - Confirm primary region outage.

2. **Database Recovery**
   - Restore from backups or activate standby.

3. **Provision OKE in DR Region**
   - Run Terraform against DR variables to stand up OKE, networking, and load balancers.

4. **GitOps Deploy**
   - Configure ArgoCD/Flux to use DR OKE context.
   - Redeploy Helm charts from Git.

5. **DNS / Traffic Cutover**
   - Update DNS and any global load balancers to point to DR.

6. **Validate**
   - Smoke tests.
   - Monitor SLOs and error budgets.

7. **Failback Planning**
   - Once primary region is stable, plan migration back with minimal downtime.
