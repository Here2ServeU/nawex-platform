# ------------------------------------------------------------------------------
# AWS DMS MODULE — database migration (full load + CDC)
# ------------------------------------------------------------------------------
# One source → target replication, as recommended by `golden.migration.database`
# (strategy "full_load_cdc"):
#
#   * replication subnet group in private subnets
#   * provisioned replication instance + replication task, or DMS Serverless
#     replication config (var.serverless)
#   * source/target endpoints whose credentials come from Secrets Manager
#     (no passwords in state) with SSL required (require/verify-ca/verify-full)
#   * KMS encryption for the instance, endpoints and task logs
#   * CloudWatch alarms on CDC source/target latency and free storage
#   * account-wide dms-vpc-role / dms-cloudwatch-logs-role only when asked
#
# Every IAM role carries var.permissions_boundary_arn (OPA plan gate).
# Tasks are created stopped (start_replication_* = false): starting a migration
# is a change-controlled action (ops/runbooks/migration/database-cutover.md).
# ------------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  partition    = data.aws_partition.current.partition
  account_id   = data.aws_caller_identity.current.account_id
  region       = data.aws_region.current.name
  kms_key_arn  = var.kms_key_arn != null ? var.kms_key_arn : aws_kms_key.this[0].arn
  instance_id  = "${var.name}-ri"
  log_group    = "dms-tasks-${local.instance_id}"
  tags         = merge(var.tags, { "golden:component" = "database-migration", "golden:dms" = var.name })
  secret_arns  = [var.source_secret_arn, var.target_secret_arn]
  service_role = var.create_dms_service_roles ? toset(["dms-vpc-role", "dms-cloudwatch-logs-role"]) : toset([])

  default_table_mappings = jsonencode({
    rules = [{
      "rule-type"      = "selection"
      "rule-id"        = "1"
      "rule-name"      = "include-${var.include_schema == "%" ? "all" : var.include_schema}"
      "object-locator" = { "schema-name" = var.include_schema, "table-name" = "%" }
      "rule-action"    = "include"
    }]
  })
  table_mappings = coalesce(var.table_mappings, local.default_table_mappings)

  default_task_settings = jsonencode({
    TargetMetadata = {
      SupportLobs        = true
      FullLobMode        = false
      LimitedSizeLobMode = true
      LobMaxSize         = var.lob_max_size_kb
    }
    FullLoadSettings = {
      # Schema is created up front (SCT / native DDL); DMS only loads data.
      TargetTablePrepMode = "DO_NOTHING"
      MaxFullLoadSubTasks = 8
    }
    ValidationSettings = {
      EnableValidation = true
      ValidationMode   = "ROW_LEVEL"
      ThreadCount      = 5
    }
    Logging = {
      EnableLogging = true
      LogComponents = [
        for c in ["SOURCE_CAPTURE", "SOURCE_UNLOAD", "TARGET_APPLY", "TARGET_LOAD", "TASK_MANAGER"] :
        { Id = c, Severity = "LOGGER_SEVERITY_DEFAULT" }
      ]
    }
    ChangeProcessingTuning = {
      BatchApplyEnabled = false
      CommitTimeout     = 1
    }
  })
  task_settings = coalesce(var.replication_task_settings, local.default_task_settings)
}

# ----------------------------------------------------------------------------- KMS
data "aws_iam_policy_document" "kms" {
  statement {
    sid       = "AccountAdmin"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:${local.partition}:iam::${local.account_id}:root"]
    }
  }
  statement {
    sid       = "CloudWatchLogs"
    actions   = ["kms:Encrypt*", "kms:Decrypt*", "kms:ReEncrypt*", "kms:GenerateDataKey*", "kms:Describe*"]
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["logs.${local.region}.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:${local.partition}:logs:${local.region}:${local.account_id}:log-group:dms-*"]
    }
  }
}

resource "aws_kms_key" "this" {
  count = var.kms_key_arn == null ? 1 : 0

  description             = "DMS ${var.name}: replication storage, endpoints and task logs"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.kms.json
  tags                    = local.tags
}

resource "aws_kms_alias" "this" {
  count = var.kms_key_arn == null ? 1 : 0

  name          = "alias/dms-${var.name}"
  target_key_id = aws_kms_key.this[0].key_id
}

# ----------------------------------------------------------------------------- IAM
data "aws_iam_policy_document" "dms_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dms.amazonaws.com"]
    }
  }
}

# Account-wide service roles DMS looks up by name. Create them once per account.
resource "aws_iam_role" "service" {
  for_each = local.service_role

  name                 = each.value
  assume_role_policy   = data.aws_iam_policy_document.dms_trust.json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = local.tags
}

resource "aws_iam_role_policy_attachment" "service" {
  for_each = local.service_role

  role = aws_iam_role.service[each.key].name
  policy_arn = (each.key == "dms-vpc-role"
    ? "arn:${local.partition}:iam::aws:policy/service-role/AmazonDMSVPCManagementRole"
    : "arn:${local.partition}:iam::aws:policy/service-role/AmazonDMSCloudWatchLogsRole"
  )
}

# Role DMS assumes to read endpoint credentials from Secrets Manager (regional principal).
data "aws_iam_policy_document" "secrets_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dms.${local.region}.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "secrets" {
  name                 = "${var.name}-dms-secrets"
  assume_role_policy   = data.aws_iam_policy_document.secrets_trust.json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = local.tags
}

data "aws_iam_policy_document" "secrets" {
  statement {
    sid       = "ReadEndpointSecrets"
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = local.secret_arns
  }
  dynamic "statement" {
    for_each = length(var.secrets_kms_key_arns) > 0 ? [1] : []
    content {
      sid       = "DecryptEndpointSecrets"
      actions   = ["kms:Decrypt"]
      resources = var.secrets_kms_key_arns
      condition {
        test     = "StringEquals"
        variable = "kms:ViaService"
        values   = ["secretsmanager.${local.region}.amazonaws.com"]
      }
    }
  }
}

resource "aws_iam_role_policy" "secrets" {
  name   = "read-endpoint-secrets"
  role   = aws_iam_role.secrets.id
  policy = data.aws_iam_policy_document.secrets.json
}

# ----------------------------------------------------------------------------- network
resource "aws_dms_replication_subnet_group" "this" {
  replication_subnet_group_id          = "${var.name}-subnets"
  replication_subnet_group_description = "DMS ${var.name} private subnets"
  subnet_ids                           = var.subnet_ids
  tags                                 = local.tags

  depends_on = [aws_iam_role_policy_attachment.service]
}

# ----------------------------------------------------------------------------- endpoints
resource "aws_dms_endpoint" "source" {
  endpoint_id                     = "${var.name}-source"
  endpoint_type                   = "source"
  engine_name                     = var.source_engine_name
  database_name                   = var.source_database_name
  secrets_manager_arn             = var.source_secret_arn
  secrets_manager_access_role_arn = aws_iam_role.secrets.arn
  ssl_mode                        = var.ssl_mode
  certificate_arn                 = var.source_certificate_arn
  kms_key_arn                     = local.kms_key_arn
  extra_connection_attributes     = var.source_extra_connection_attributes
  tags                            = local.tags

  depends_on = [aws_iam_role_policy.secrets]
}

resource "aws_dms_endpoint" "target" {
  endpoint_id                     = "${var.name}-target"
  endpoint_type                   = "target"
  engine_name                     = var.target_engine_name
  database_name                   = var.target_database_name
  secrets_manager_arn             = var.target_secret_arn
  secrets_manager_access_role_arn = aws_iam_role.secrets.arn
  ssl_mode                        = var.ssl_mode
  certificate_arn                 = var.target_certificate_arn
  kms_key_arn                     = local.kms_key_arn
  extra_connection_attributes     = var.target_extra_connection_attributes
  tags                            = local.tags

  depends_on = [aws_iam_role_policy.secrets]
}

# ----------------------------------------------------------------------------- provisioned
resource "aws_cloudwatch_log_group" "tasks" {
  count = var.serverless ? 0 : 1

  # DMS writes task logs to dms-tasks-<replication instance id>; pre-create it for KMS + retention.
  name              = local.log_group
  retention_in_days = var.log_retention_days
  kms_key_id        = local.kms_key_arn
  tags              = local.tags
}

resource "aws_dms_replication_instance" "this" {
  count = var.serverless ? 0 : 1

  replication_instance_id      = local.instance_id
  replication_instance_class   = var.replication_instance_class
  allocated_storage            = var.allocated_storage_gb
  engine_version               = var.engine_version
  multi_az                     = var.multi_az
  publicly_accessible          = false
  kms_key_arn                  = local.kms_key_arn
  replication_subnet_group_id  = aws_dms_replication_subnet_group.this.id
  vpc_security_group_ids       = var.security_group_ids
  preferred_maintenance_window = var.preferred_maintenance_window
  auto_minor_version_upgrade   = true
  allow_major_version_upgrade  = false
  apply_immediately            = false
  tags                         = local.tags

  depends_on = [aws_iam_role_policy_attachment.service, aws_cloudwatch_log_group.tasks]
}

resource "aws_dms_replication_task" "this" {
  count = var.serverless ? 0 : 1

  replication_task_id       = "${var.name}-task"
  migration_type            = var.migration_type
  replication_instance_arn  = aws_dms_replication_instance.this[0].replication_instance_arn
  source_endpoint_arn       = aws_dms_endpoint.source.endpoint_arn
  target_endpoint_arn       = aws_dms_endpoint.target.endpoint_arn
  table_mappings            = local.table_mappings
  replication_task_settings = local.task_settings
  start_replication_task    = false
  tags                      = local.tags

  lifecycle {
    # DMS rewrites settings with defaults; avoid perpetual diffs.
    ignore_changes = [replication_task_settings]
  }
}

# ----------------------------------------------------------------------------- serverless
resource "aws_dms_replication_config" "this" {
  count = var.serverless ? 1 : 0

  replication_config_identifier = "${var.name}-config"
  replication_type              = var.migration_type
  source_endpoint_arn           = aws_dms_endpoint.source.endpoint_arn
  target_endpoint_arn           = aws_dms_endpoint.target.endpoint_arn
  table_mappings                = local.table_mappings
  replication_settings          = local.task_settings
  start_replication             = false
  tags                          = local.tags

  compute_config {
    replication_subnet_group_id  = aws_dms_replication_subnet_group.this.id
    vpc_security_group_ids       = var.security_group_ids
    min_capacity_units           = var.serverless_min_capacity_units
    max_capacity_units           = var.serverless_max_capacity_units
    multi_az                     = var.multi_az
    kms_key_id                   = local.kms_key_arn
    preferred_maintenance_window = var.preferred_maintenance_window
  }

  lifecycle {
    ignore_changes = [replication_settings]
  }

  depends_on = [aws_iam_role_policy_attachment.service]
}

# ----------------------------------------------------------------------------- alarms
locals {
  # Task metrics are dimensioned by instance identifier + task resource id (last ARN segment).
  task_resource_id = var.serverless ? "" : element(split(":", aws_dms_replication_task.this[0].replication_task_arn), 6)
  cdc_metrics      = var.serverless || var.migration_type == "full-load" ? toset([]) : toset(["CDCLatencySource", "CDCLatencyTarget"])
}

resource "aws_cloudwatch_metric_alarm" "cdc_latency" {
  for_each = local.cdc_metrics

  alarm_name          = "${var.name}-dms-${each.value}"
  alarm_description   = "DMS ${var.name}: ${each.value} above ${var.cdc_latency_threshold_seconds}s — replication is falling behind (see ops/runbooks/migration/database-cutover.md)."
  namespace           = "AWS/DMS"
  metric_name         = each.value
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = var.cdc_latency_evaluation_periods
  threshold           = var.cdc_latency_threshold_seconds
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
  tags                = local.tags

  dimensions = {
    ReplicationInstanceIdentifier = local.instance_id
    ReplicationTaskIdentifier     = local.task_resource_id
  }
}

resource "aws_cloudwatch_metric_alarm" "free_storage" {
  count = var.serverless ? 0 : 1

  alarm_name          = "${var.name}-dms-free-storage"
  alarm_description   = "DMS ${var.name}: replication instance storage below 20% (cached changes / logs)."
  namespace           = "AWS/DMS"
  metric_name         = "FreeStorageSpace"
  statistic           = "Minimum"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.allocated_storage_gb * 1024 * 1024 * 1024 * 0.2
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
  tags                = local.tags

  dimensions = {
    ReplicationInstanceIdentifier = local.instance_id
  }
}
