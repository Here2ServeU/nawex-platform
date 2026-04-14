# PostgreSQL Database Failover Playbook for Backstage IDP

## Goals
- Execute a controlled failover of the primary Backstage PostgreSQL database with minimal downtime and data loss.
- Ensure application services quickly reconnect to the new primary instance.

## Preconditions
- Managed service (e.g., AWS RDS, Azure Database for PostgreSQL, Cloud SQL) or self-managed with streaming replication.
- At least one healthy, synchronized read replica available in the primary or DR region.

## Steps

1. **Confirm Incident and Backup**
- Check metrics: replication lag, active connections, and primary errors.
- Validate that the primary is truly unhealthy or confirm a pre-planned failover.
- **Verify the status and time of the last successful backup.**

2. **Isolate Primary and Promote Replica**
- Temporarily scale down/block traffic to the old primary instance.
- For managed DB: Use console/CLI to promote the designated read replica to the new primary instance.
- For self-managed: Run `pg_ctl promote` or equivalent on the replica host.

3. **Update Kubernetes Configuration (GitOps)**
- **Update connection endpoints/credentials** in the central source of truth:
- **Kubernetes Secrets** (if storing credentials externally).
- **ConfigMap Generation Source** (to update the host if needed).
- Trigger the **GitOps deployment** to propagate the new connection string to the Backstage deployment.

4. **Verify Application Health**
- Run application smoke tests against core NRP services.
- Check the Backstage health status (`/healthcheck` endpoint).
- **Confirm Backstage Catalog Entities are being processed** without database connection errors.
- Monitor application error rates and latency via observability dashboards.

5. **Post-Failover Tasks**
- Plan re-seeding or re-adding the old primary as a replica or standby instance if the host is healthy.
- Document the incident timeline and performance metrics during the failover window.

---

*Copyright (c) 2026 Nawex Platform (NAWEX). Owned by Rev. Dr. Emmanuel Naweji. All rights reserved.*
