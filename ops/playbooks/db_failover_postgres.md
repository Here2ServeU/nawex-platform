# Postgres Database Failover Playbook

## Preconditions
- Managed service (e.g., AWS RDS, Azure Database for PostgreSQL, Cloud SQL) or self-managed with streaming replication.
- At least one healthy replica.

## Steps

1. **Confirm Incident**
   - Check metrics: replication lag, connections, errors.
   - Validate that primary is truly unhealthy, not just slow.

2. **Promote Replica**
   - For managed DB:
     - Use console/CLI to promote read replica to primary.
   - For self-managed:
     - Run `pg_ctl promote` or equivalent on replica.

3. **Update Connection Strings**
   - Update connection endpoints in:
     - Kubernetes Secrets
     - Terraform/Helm values if needed
   - Trigger GitOps deployment to propagate.

4. **Verify**
   - Run health checks.
   - Run application smoke tests.
   - Monitor error rates and latency.

5. **Post-Failover**
   - Plan re-seeding or re-adding old primary as replica if healthy.
