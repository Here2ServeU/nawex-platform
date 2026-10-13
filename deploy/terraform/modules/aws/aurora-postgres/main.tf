# ------------------------------------------------------------------------------
# AURORA POSTGRESQL MODULE — performance-tuned, observable, pooled
# ------------------------------------------------------------------------------
# One Aurora PostgreSQL cluster configured for the tuning workflow in
# docs/database/README.md (`golden db workload|explain|indexes|capacity`):
#
#   * storage encryption with KMS (module key unless var.kms_key_arn), IAM
#     database authentication, master password managed by Secrets Manager
#   * Aurora Standard or I/O-Optimized storage (var.io_optimized — decide with
#     `golden db capacity`, break-even when I/O ≥ ~25 % of the bill)
#   * cluster + instance parameter groups: pg_stat_statements and auto_explain
#     preloaded, slow-query logging, track_io_timing, idle-in-transaction
#     timeout, SSD random_page_cost, lock-wait / temp-file / autovacuum logging
#   * Performance Insights (KMS, retention) and Enhanced Monitoring on every
#     instance
#   * RDS Proxy (Secrets Manager auth, TLS required, pool limits, read-only
#     endpoint when readers exist)
#   * optional reader auto scaling on CPU or connections
#   * backups, deletion protection, final snapshot
#   * CloudWatch alarms: CPU, freeable memory, connections vs max_connections,
#     replica lag, deadlocks, transaction-ID age (wraparound)
#
# Every IAM role carries var.permissions_boundary_arn (OPA plan gate).
# ------------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  partition    = data.aws_partition.current.partition
  account_id   = data.aws_caller_identity.current.account_id
  region       = data.aws_region.current.name
  major        = split(".", var.engine_version)[0]
  family       = "aurora-postgresql${local.major}"
  kms_key_arn  = var.kms_key_arn != null ? var.kms_key_arn : aws_kms_key.this[0].arn
  tags         = merge(var.tags, { "golden:component" = "database", "golden:aurora" = var.name })
  instance_ids = [for i in range(var.instance_count) : "${var.name}-${i + 1}"]
  reader_ids   = slice(local.instance_ids, 1, length(local.instance_ids))
  proxy_secret_arns = length(var.proxy_auth_secret_arns) > 0 ? var.proxy_auth_secret_arns : [
    aws_rds_cluster.this.master_user_secret[0].secret_arn
  ]

  # Cluster-level settings. Each value is the reasoning-backed default from
  # docs/database/README.md; apply_method "pending-reboot" for static GUCs.
  cluster_parameters = concat([
    # Statement-level statistics (golden db workload) and plans of slow queries.
    { name = "shared_preload_libraries", value = "pg_stat_statements,auto_explain", apply_method = "pending-reboot" },
    { name = "pg_stat_statements.track", value = "top", apply_method = "immediate" },
    { name = "pg_stat_statements.max", value = "10000", apply_method = "pending-reboot" },
    { name = "track_activity_query_size", value = "4096", apply_method = "pending-reboot" },
    # Per-query I/O time in pg_stat_statements / EXPLAIN BUFFERS (cheap on Nitro clocks).
    { name = "track_io_timing", value = "1", apply_method = "immediate" },
    # Log statements slower than this (ms); auto_explain logs their plans.
    { name = "log_min_duration_statement", value = tostring(var.log_min_duration_statement_ms), apply_method = "immediate" },
    { name = "auto_explain.log_min_duration", value = tostring(var.auto_explain_min_duration_ms), apply_method = "immediate" },
    { name = "auto_explain.log_analyze", value = "1", apply_method = "immediate" },
    # Per-node timing is the expensive part of ANALYZE; row counts and buffers are cheap.
    { name = "auto_explain.log_timing", value = "0", apply_method = "immediate" },
    { name = "auto_explain.log_buffers", value = "1", apply_method = "immediate" },
    { name = "auto_explain.log_format", value = "json", apply_method = "immediate" },
    { name = "auto_explain.log_nested_statements", value = "1", apply_method = "immediate" },
    # Sessions idle inside a transaction hold locks and the xmin horizon (bloat).
    { name = "idle_in_transaction_session_timeout", value = tostring(var.idle_in_transaction_timeout_ms), apply_method = "immediate" },
    # Aurora storage is SSD-backed: random reads are ~as cheap as sequential ones.
    { name = "random_page_cost", value = tostring(var.random_page_cost), apply_method = "immediate" },
    # Lock waits longer than deadlock_timeout (1s), temp files > 10MB, slow autovacuum runs.
    { name = "log_lock_waits", value = "1", apply_method = "immediate" },
    { name = "log_temp_files", value = "10240", apply_method = "immediate" },
    { name = "log_autovacuum_min_duration", value = "1000", apply_method = "immediate" },
    { name = "rds.force_ssl", value = "1", apply_method = "immediate" },
  ], var.extra_cluster_parameters)

  # Instance-level settings; size them with `golden db capacity` (memory_parameters).
  instance_parameters = concat([
    { name = "work_mem", value = tostring(var.work_mem_kb), apply_method = "immediate" },
    { name = "maintenance_work_mem", value = tostring(var.maintenance_work_mem_kb), apply_method = "immediate" },
  ], var.extra_instance_parameters)
}

# ------------------------------------------------------------------------- KMS
resource "aws_kms_key" "this" {
  count = var.kms_key_arn == null ? 1 : 0

  description             = "Aurora ${var.name}: storage, Performance Insights, master secret"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = local.tags
}

resource "aws_kms_alias" "this" {
  count = var.kms_key_arn == null ? 1 : 0

  name          = "alias/aurora-${var.name}"
  target_key_id = aws_kms_key.this[0].key_id
}

# ------------------------------------------------------------------------- network
resource "aws_db_subnet_group" "this" {
  name        = "${var.name}-aurora"
  description = "Aurora ${var.name} private subnets"
  subnet_ids  = var.subnet_ids
  tags        = local.tags
}

# ------------------------------------------------------------------------- parameter groups
resource "aws_rds_cluster_parameter_group" "this" {
  name_prefix = "${var.name}-cluster-"
  family      = local.family
  description = "Aurora ${var.name}: observability + tuning (docs/database/README.md)"
  tags        = local.tags

  dynamic "parameter" {
    for_each = local.cluster_parameters
    content {
      name         = parameter.value.name
      value        = parameter.value.value
      apply_method = parameter.value.apply_method
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_db_parameter_group" "this" {
  name_prefix = "${var.name}-instance-"
  family      = local.family
  description = "Aurora ${var.name}: instance memory settings"
  tags        = local.tags

  dynamic "parameter" {
    for_each = local.instance_parameters
    content {
      name         = parameter.value.name
      value        = parameter.value.value
      apply_method = parameter.value.apply_method
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ------------------------------------------------------------------------- cluster
resource "aws_rds_cluster" "this" {
  cluster_identifier = var.name
  engine             = "aurora-postgresql"
  engine_version     = var.engine_version
  database_name      = var.database_name
  master_username    = var.master_username

  # Password generated and rotated by Secrets Manager; never in state.
  manage_master_user_password   = true
  master_user_secret_kms_key_id = local.kms_key_arn

  storage_encrypted                   = true
  kms_key_id                          = local.kms_key_arn
  storage_type                        = var.io_optimized ? "aurora-iopt1" : null
  iam_database_authentication_enabled = true

  db_subnet_group_name            = aws_db_subnet_group.this.name
  vpc_security_group_ids          = var.security_group_ids
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.this.name
  port                            = 5432

  backup_retention_period      = var.backup_retention_days
  preferred_backup_window      = var.preferred_backup_window
  preferred_maintenance_window = var.preferred_maintenance_window
  copy_tags_to_snapshot        = true
  deletion_protection          = var.deletion_protection
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${var.name}-final"

  enabled_cloudwatch_logs_exports = ["postgresql"]
  apply_immediately               = var.apply_immediately
  tags                            = local.tags

  lifecycle {
    # The final snapshot id only matters at destroy time; do not churn on it.
    ignore_changes = [final_snapshot_identifier]
  }
}

resource "aws_rds_cluster_instance" "this" {
  for_each = { for i, id in local.instance_ids : id => i }

  identifier              = each.key
  cluster_identifier      = aws_rds_cluster.this.id
  engine                  = aws_rds_cluster.this.engine
  engine_version          = aws_rds_cluster.this.engine_version
  instance_class          = var.instance_class
  db_parameter_group_name = aws_db_parameter_group.this.name
  db_subnet_group_name    = aws_db_subnet_group.this.name
  publicly_accessible     = false
  promotion_tier          = each.value == 0 ? 0 : 1

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = local.kms_key_arn
  performance_insights_retention_period = var.performance_insights_retention_days

  monitoring_interval = var.monitoring_interval
  monitoring_role_arn = var.monitoring_interval > 0 ? aws_iam_role.monitoring[0].arn : null

  auto_minor_version_upgrade = true
  apply_immediately          = var.apply_immediately
  tags                       = local.tags
}

# ------------------------------------------------------------------------- enhanced monitoring
data "aws_iam_policy_document" "monitoring_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "monitoring" {
  count = var.monitoring_interval > 0 ? 1 : 0

  name                 = "${var.name}-rds-monitoring"
  assume_role_policy   = data.aws_iam_policy_document.monitoring_assume.json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = local.tags
}

resource "aws_iam_role_policy_attachment" "monitoring" {
  count = var.monitoring_interval > 0 ? 1 : 0

  role       = aws_iam_role.monitoring[0].name
  policy_arn = "arn:${local.partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ------------------------------------------------------------------------- RDS Proxy
data "aws_iam_policy_document" "proxy_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["rds.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

data "aws_iam_policy_document" "proxy_secrets" {
  statement {
    sid       = "ReadDatabaseCredentials"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = local.proxy_secret_arns
  }
  statement {
    sid       = "DecryptViaSecretsManager"
    actions   = ["kms:Decrypt"]
    resources = [local.kms_key_arn]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["secretsmanager.${local.region}.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "proxy" {
  count = var.enable_proxy ? 1 : 0

  name                 = "${var.name}-rds-proxy"
  assume_role_policy   = data.aws_iam_policy_document.proxy_assume.json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = local.tags
}

resource "aws_iam_role_policy" "proxy" {
  count = var.enable_proxy ? 1 : 0

  name   = "secrets"
  role   = aws_iam_role.proxy[0].id
  policy = data.aws_iam_policy_document.proxy_secrets.json
}

resource "aws_db_proxy" "this" {
  count = var.enable_proxy ? 1 : 0

  name                   = var.name
  engine_family          = "POSTGRESQL"
  role_arn               = aws_iam_role.proxy[0].arn
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = var.security_group_ids
  require_tls            = true
  idle_client_timeout    = var.proxy_idle_client_timeout
  debug_logging          = false
  tags                   = local.tags

  dynamic "auth" {
    for_each = local.proxy_secret_arns
    content {
      auth_scheme = "SECRETS"
      iam_auth    = var.proxy_iam_auth
      secret_arn  = auth.value
    }
  }
}

resource "aws_db_proxy_default_target_group" "this" {
  count = var.enable_proxy ? 1 : 0

  db_proxy_name = aws_db_proxy.this[0].name

  connection_pool_config {
    # Share of max_connections the proxy may open; leave headroom for admin,
    # replication and migrations.
    max_connections_percent      = var.proxy_max_connections_percent
    max_idle_connections_percent = var.proxy_max_idle_connections_percent
    connection_borrow_timeout    = var.proxy_connection_borrow_timeout
    # SET statements would pin a client to one server connection; allow them.
    session_pinning_filters = ["EXCLUDE_VARIABLE_SETS"]
  }
}

resource "aws_db_proxy_target" "this" {
  count = var.enable_proxy ? 1 : 0

  db_proxy_name         = aws_db_proxy.this[0].name
  target_group_name     = aws_db_proxy_default_target_group.this[0].name
  db_cluster_identifier = aws_rds_cluster.this.cluster_identifier
}

resource "aws_db_proxy_endpoint" "read_only" {
  count = var.enable_proxy && var.instance_count > 1 ? 1 : 0

  db_proxy_name          = aws_db_proxy.this[0].name
  db_proxy_endpoint_name = "${var.name}-ro"
  vpc_subnet_ids         = var.subnet_ids
  vpc_security_group_ids = var.security_group_ids
  target_role            = "READ_ONLY"
  tags                   = local.tags
}

# ------------------------------------------------------------------------- reader auto scaling
resource "aws_appautoscaling_target" "readers" {
  count = var.reader_autoscaling_enabled ? 1 : 0

  service_namespace  = "rds"
  scalable_dimension = "rds:cluster:ReadReplicaCount"
  resource_id        = "cluster:${aws_rds_cluster.this.id}"
  min_capacity       = var.reader_min_capacity
  max_capacity       = var.reader_max_capacity

  depends_on = [aws_rds_cluster_instance.this]
}

resource "aws_appautoscaling_policy" "readers" {
  count = var.reader_autoscaling_enabled ? 1 : 0

  name               = "${var.name}-readers-${var.reader_autoscaling_metric}"
  policy_type        = "TargetTrackingScaling"
  service_namespace  = aws_appautoscaling_target.readers[0].service_namespace
  scalable_dimension = aws_appautoscaling_target.readers[0].scalable_dimension
  resource_id        = aws_appautoscaling_target.readers[0].resource_id

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = var.reader_autoscaling_metric == "cpu" ? "RDSReaderAverageCPUUtilization" : "RDSReaderAverageDatabaseConnections"
    }
    target_value       = var.reader_autoscaling_target
    scale_in_cooldown  = var.reader_scale_in_cooldown
    scale_out_cooldown = var.reader_scale_out_cooldown
  }
}

# ------------------------------------------------------------------------- alarms
locals {
  # Per-instance alarms (writer and readers); replica lag is readers-only below.
  instance_alarms = {
    cpu = {
      metric      = "CPUUtilization"
      statistic   = "Average"
      comparison  = "GreaterThanThreshold"
      threshold   = var.cpu_alarm_threshold
      description = "CPU above ${var.cpu_alarm_threshold}% — run `golden db workload` on a pg_stat_statements export"
    }
    freeable_memory = {
      metric      = "FreeableMemory"
      statistic   = "Minimum"
      comparison  = "LessThanThreshold"
      threshold   = var.freeable_memory_alarm_bytes
      description = "Freeable memory low — check work_mem × connections (golden db capacity)"
    }
    connections = {
      metric      = "DatabaseConnections"
      statistic   = "Maximum"
      comparison  = "GreaterThanThreshold"
      threshold   = floor(var.max_connections * var.connection_alarm_ratio)
      description = "Connections above ${var.connection_alarm_ratio * 100}% of max_connections (${var.max_connections}) — pool via RDS Proxy / PgBouncer"
    }
    deadlocks = {
      metric      = "Deadlocks"
      statistic   = "Sum"
      comparison  = "GreaterThanThreshold"
      threshold   = var.deadlock_alarm_threshold
      description = "Deadlocks detected — see ops/runbooks/playbooks/database_performance.md (lock ordering)"
    }
    xid_age = {
      metric      = "MaximumUsedTransactionIDs"
      statistic   = "Maximum"
      comparison  = "GreaterThanThreshold"
      threshold   = var.xid_age_alarm_threshold
      description = "Transaction ID age high — wraparound risk; VACUUM (FREEZE) the oldest tables"
    }
  }
  alarm_pairs = merge([
    for id in local.instance_ids : {
      for k, a in local.instance_alarms : "${id}/${k}" => merge(a, { instance = id, key = k })
    }
  ]...)
}

resource "aws_cloudwatch_metric_alarm" "instance" {
  for_each = local.alarm_pairs

  alarm_name          = "${each.value.instance}-${each.value.key}"
  alarm_description   = "Aurora ${each.value.instance}: ${each.value.description}."
  namespace           = "AWS/RDS"
  metric_name         = each.value.metric
  statistic           = each.value.statistic
  period              = 300
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = each.value.threshold
  comparison_operator = each.value.comparison
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
  tags                = local.tags

  dimensions = {
    DBInstanceIdentifier = each.value.instance
  }

  depends_on = [aws_rds_cluster_instance.this]
}

resource "aws_cloudwatch_metric_alarm" "replica_lag" {
  for_each = toset(local.reader_ids)

  alarm_name          = "${each.key}-replica-lag"
  alarm_description   = "Aurora ${each.key}: AuroraReplicaLag above ${var.replica_lag_alarm_ms} ms — readers serve stale data."
  namespace           = "AWS/RDS"
  metric_name         = "AuroraReplicaLag"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 5
  threshold           = var.replica_lag_alarm_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
  tags                = local.tags

  dimensions = {
    DBInstanceIdentifier = each.key
  }

  depends_on = [aws_rds_cluster_instance.this]
}
