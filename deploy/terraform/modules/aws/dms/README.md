# AWS DMS module

Full load + CDC database migration for one source → target pair, the `full_load_cdc` strategy chosen by
`golden.migration.database` (see [docs/modernization/database-migration.md](../../../../../docs/modernization/database-migration.md)).

| Creates | Notes |
|---|---|
| Replication subnet group | Private subnets in ≥ 2 AZs |
| Replication instance + task **or** serverless replication config | `serverless = true` switches to `aws_dms_replication_config` |
| Source / target endpoints | Credentials from Secrets Manager (`*_secret_arn`); `ssl_mode` is `require`, `verify-ca` or `verify-full` |
| Secrets access role | Assumed by `dms.<region>.amazonaws.com`, scoped to the two secrets (+ optional KMS keys) |
| `dms-vpc-role`, `dms-cloudwatch-logs-role` | Only with `create_dms_service_roles = true` (account-wide, create once) |
| KMS key (unless `kms_key_arn` is given) | Instance storage, endpoints, task log group |
| CloudWatch alarms | `CDCLatencySource`, `CDCLatencyTarget`, `FreeStorageSpace` (provisioned mode) |

Every `aws_iam_role` sets `permissions_boundary = var.permissions_boundary_arn`, as the OPA plan gate
(`security/policies/opa/aws-iam.rego`) requires. Tasks are created **stopped**; starting one is a
change-controlled step in [database-cutover.md](../../../../../ops/runbooks/migration/database-cutover.md).

```hcl
module "dms_reporting" {
  source = "../../modules/aws/dms"

  name               = "reporting-ora-to-aurora"
  subnet_ids         = module.vpc.private_subnets
  security_group_ids = [aws_security_group.dms.id]

  source_engine_name   = "oracle"
  source_database_name = "REPORTING"
  source_secret_arn    = aws_secretsmanager_secret.reporting_source.arn
  target_engine_name   = "aurora-postgresql"
  target_database_name = "reporting"
  target_secret_arn    = aws_secretsmanager_secret.reporting_target.arn
  ssl_mode             = "verify-full"
  source_certificate_arn = aws_dms_certificate.onprem_ca.certificate_arn
  target_certificate_arn = aws_dms_certificate.rds_ca.certificate_arn

  table_mappings = file("${path.module}/mappings/reporting.json")

  permissions_boundary_arn = module.permission_boundary.arn
  alarm_actions            = [aws_sns_topic.migration.arn]
}
```

Notes

- Alarms are created for provisioned mode only; for serverless, alarm on the replication config's
  metrics once its identifier is known.
- `replication_task_settings` drifts because DMS fills in defaults; the module ignores changes to it.
  Change settings by replacing the task in a maintenance window.
- Size the instance from the planner's CDC numbers (`peak_gb_per_hour` vs. apply rate) and a rehearsal.
