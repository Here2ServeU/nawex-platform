# Database access tier (`golden-db`)

Connection pooling and metrics for the Aurora PostgreSQL cluster created by
[`deploy/terraform/modules/aws/aurora-postgres`](../../terraform/modules/aws/aurora-postgres/README.md).
Design notes: [docs/database/README.md](../../../docs/database/README.md).

| File | What |
|---|---|
| `namespace.yaml` | `golden-db`, Pod Security `restricted` |
| `externalsecret.yaml` | `pgbouncer-auth` (userlist + stats password) and `postgres-exporter-dsn` from ClusterSecretStore `golden-secrets` |
| `pgbouncer.yaml` | PgBouncer **transaction pooling** (2 replicas, zone spread, PDB) + `pgbouncer-exporter` sidecar on 9127 |
| `postgres-exporter.yaml` | postgres_exporter on 9187 with custom queries: top `pg_stat_statements`, long transactions, blocked sessions, XID age |
| `networkpolicy.yaml` | default deny; apps labelled `golden.io/db-client=true` → 6432; Prometheus (`monitoring`) → metrics; egress only to 5432 and DNS |

```bash
kubectl apply -k deploy/k8s/database
# app connection string (read/write and read-only pools):
#   postgresql://app_user@pgbouncer.golden-db.svc:6432/app
#   postgresql://app_user@pgbouncer.golden-db.svc:6432/app_ro
```

**Sizing.** `default_pool_size`, `reserve_pool_size` and `max_client_conn` come from
`golden db capacity` (`golden.database.capacity.pool_sizing`): active server connections
≈ `cores × 2 + 1` across all PgBouncer replicas, far below `max_connections`. Re-run it when the
instance class or the number of app pods changes.

**PgBouncer or RDS Proxy?** RDS Proxy (enabled by default in the Terraform module) is managed, keeps
client connections through failovers and supports IAM auth; PgBouncer is cheaper, runs next to the
apps (one less network hop), and its transaction pooling is more aggressive (RDS Proxy pins sessions
on some statements). Use one in the request path, not both chained.

Replace the placeholder Aurora hostnames and the `10.0.0.0/8` egress CIDR with your environment's
values. Pin images by digest in production. All built-in kinds pass `kubeconform -strict`; the
Deployments pass `security/policies/opa/k8s-security.rego`.
