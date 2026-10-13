# Aurora PostgreSQL module

A performance-tuned, observable Aurora PostgreSQL cluster — the infrastructure half of the database
optimization capability ([docs/database/README.md](../../../../../docs/database/README.md)).

| Creates | Notes |
|---|---|
| `aws_rds_cluster` | KMS storage encryption, IAM database auth, master password managed by Secrets Manager, `io_optimized` → `aurora-iopt1`, backups, deletion protection, final snapshot, `postgresql` log export |
| `aws_rds_cluster_instance` × `instance_count` | Writer + readers; Performance Insights (KMS, retention) and Enhanced Monitoring |
| Cluster parameter group | `pg_stat_statements` + `auto_explain` preloaded, `log_min_duration_statement`, `track_io_timing`, `idle_in_transaction_session_timeout`, `random_page_cost = 1.1`, lock-wait / temp-file / autovacuum logging, `rds.force_ssl` |
| Instance parameter group | `work_mem`, `maintenance_work_mem` (size with `golden db capacity`) |
| RDS Proxy | Secrets Manager auth (TLS required, IAM auth by default), pool limits, read-only endpoint when readers exist |
| Reader auto scaling | Optional target tracking on reader CPU or connections |
| CloudWatch alarms | CPU, FreeableMemory, DatabaseConnections vs `max_connections`, Deadlocks, MaximumUsedTransactionIDs (per instance); AuroraReplicaLag (per reader) |
| IAM roles | Enhanced Monitoring, RDS Proxy — both with `permissions_boundary = var.permissions_boundary_arn` (OPA plan gate) |

```hcl
module "payments_db" {
  source = "../../modules/aws/aurora-postgres"

  name               = "golden-payments"
  subnet_ids         = module.vpc.database_subnets
  security_group_ids = [aws_security_group.payments_db.id]

  engine_version  = "16.4"
  instance_class  = "db.r7g.2xlarge"  # from `golden db capacity`
  instance_count  = 2
  io_optimized    = true              # I/O ≥ ~25 % of the bill
  max_connections = 2500              # SHOW max_connections on this class (alarm denominator)
  work_mem_kb     = 65536

  reader_autoscaling_enabled = true
  reader_max_capacity        = 4

  performance_insights_retention_days = 31
  permissions_boundary_arn            = module.permission_boundary.arn
  alarm_actions                       = [aws_sns_topic.db_alerts.arn]
}
```

Notes

- `shared_preload_libraries` is static: the first apply leaves the cluster in `pending-reboot`; reboot
  in a maintenance window, then `CREATE EXTENSION pg_stat_statements;` in each database.
- `auto_explain.log_timing = 0` keeps the overhead of `log_analyze` low (row counts and buffers only).
- Readers added by auto scaling are not in Terraform state and have no per-instance alarms; the
  cluster-level `AuroraReplicaLag` of Terraform-managed readers still covers lag.
- Parameter values are starting points; `golden db capacity` (`memory_parameters`) derives them from the
  instance class and connection count.
