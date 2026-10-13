# ------------------------------------------------------------------------------
# AWS FINOPS MODULE (Budgets, Cost Anomaly Detection, FOCUS export, cost tags)
# ------------------------------------------------------------------------------
# The "Inform" and "Operate" layers of the FinOps lifecycle for one AWS account
# (or a whole consolidated billing family when applied in the payer account).
#
#   Budgets            account budget, optional per-linked-account budgets and
#                      per-team budgets filtered on the team cost allocation tag;
#                      ACTUAL and FORECASTED notifications to SNS and email
#   Anomaly Detection  one SERVICE monitor + one cost-allocation-tag monitor
#                      (team), subscribed IMMEDIATE to SNS and DAILY to email
#                      when impact >= anomaly_threshold_usd OR _percent
#   Data Export        CUR 2.0 family export of the FOCUS 1.0 table, Parquet,
#                      daily refresh, into a KMS-encrypted, versioned,
#                      public-access-blocked, TLS-only S3 bucket
#   Cost tags          activates required_tags as cost allocation tags so the
#                      tags show up in Cost Explorer, budgets and the export
#
# Tag enforcement at plan time lives in security/policies/opa/tagging.rego; the
# exported FOCUS data is analysed by golden.finops (showback, anomalies,
# recommendations). See docs/finops/README.md.
#
# Notes
#   * Billing APIs (Budgets, Cost Explorer, Data Exports) are global but served
#     from us-east-1: call this module with a us-east-1 provider.
#   * Cost allocation tags can only be activated from the payer account and
#     only after the tag key has appeared on a billed resource (up to 24h).
# ------------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  account_id    = data.aws_caller_identity.current.account_id
  partition     = data.aws_partition.current.partition
  region        = data.aws_region.current.name
  bucket_name   = var.export_bucket_name != "" ? var.export_bucket_name : "${var.name_prefix}-billing-exports-${local.account_id}"
  monitor_teams = length(var.anomaly_monitor_teams) > 0 ? var.anomaly_monitor_teams : keys(var.team_budgets)

  notifications = concat(
    [for t in var.actual_thresholds : { type = "ACTUAL", threshold = t }],
    [for t in var.forecast_thresholds : { type = "FORECASTED", threshold = t }],
  )
}

# ----------------------------------------------------------------------------- encryption
# One customer-managed key for the alert topic and the export bucket. The
# billing services need explicit key grants to publish/write encrypted data.
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
    sid       = "BillingServicesUseKey"
    actions   = ["kms:GenerateDataKey*", "kms:Decrypt"]
    resources = ["*"]
    principals {
      type = "Service"
      identifiers = [
        "budgets.amazonaws.com",
        "costalerts.amazonaws.com",
        "bcm-data-exports.amazonaws.com",
        "billingreports.amazonaws.com",
      ]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_kms_key" "finops" {
  description             = "${var.name_prefix} FinOps alerts and billing exports"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.kms.json
  tags                    = var.tags
}

resource "aws_kms_alias" "finops" {
  name          = "alias/${var.name_prefix}-finops"
  target_key_id = aws_kms_key.finops.key_id
}

# ----------------------------------------------------------------------------- alert topic
resource "aws_sns_topic" "alerts" {
  name              = "${var.name_prefix}-finops-alerts"
  kms_master_key_id = aws_kms_key.finops.arn
  tags              = var.tags
}

data "aws_iam_policy_document" "alerts" {
  statement {
    sid       = "BillingServicesPublish"
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com", "costalerts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts.json
}

resource "aws_sns_topic_subscription" "email" {
  for_each  = toset(var.notification_emails)
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

# ----------------------------------------------------------------------------- budgets
resource "aws_budgets_budget" "account" {
  name         = "${var.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget)
  limit_unit   = var.currency
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = local.notifications
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.threshold
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_email_addresses = var.notification_emails
      subscriber_sns_topic_arns  = [aws_sns_topic.alerts.arn]
    }
  }

  tags       = var.tags
  depends_on = [aws_sns_topic_policy.alerts]
}

resource "aws_budgets_budget" "linked_account" {
  for_each     = var.linked_account_budgets
  name         = "${var.name_prefix}-account-${each.key}"
  budget_type  = "COST"
  limit_amount = tostring(each.value)
  limit_unit   = var.currency
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "LinkedAccount"
    values = [each.key]
  }

  dynamic "notification" {
    for_each = local.notifications
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.threshold
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_email_addresses = var.notification_emails
      subscriber_sns_topic_arns  = [aws_sns_topic.alerts.arn]
    }
  }

  tags       = var.tags
  depends_on = [aws_sns_topic_policy.alerts]
}

resource "aws_budgets_budget" "team" {
  for_each     = var.team_budgets
  name         = "${var.name_prefix}-team-${lower(each.key)}"
  budget_type  = "COST"
  limit_amount = tostring(each.value)
  limit_unit   = var.currency
  time_unit    = "MONTHLY"

  # Cost allocation tag filter format: user:<key>$<value>
  cost_filter {
    name   = "TagKeyValue"
    values = ["user:${var.team_tag_key}$${each.key}"]
  }

  dynamic "notification" {
    for_each = local.notifications
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.threshold
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_email_addresses = var.notification_emails
      subscriber_sns_topic_arns  = [aws_sns_topic.alerts.arn]
    }
  }

  tags       = var.tags
  depends_on = [aws_sns_topic_policy.alerts]
}

# ----------------------------------------------------------------------------- anomaly detection
resource "aws_ce_anomaly_monitor" "service" {
  name              = "${var.name_prefix}-services"
  monitor_type      = "DIMENSIONAL"
  monitor_dimension = "SERVICE"
  tags              = var.tags
}

resource "aws_ce_anomaly_monitor" "team" {
  count        = length(local.monitor_teams) > 0 ? 1 : 0
  name         = "${var.name_prefix}-teams"
  monitor_type = "CUSTOM"

  # Full object shape avoids a perpetual diff against the normalised API value.
  monitor_specification = jsonencode({
    And            = null
    CostCategories = null
    Dimensions     = null
    Not            = null
    Or             = null
    Tags = {
      Key          = var.team_tag_key
      MatchOptions = null
      Values       = local.monitor_teams
    }
  })

  tags = var.tags
}

locals {
  monitor_arns = concat(
    [aws_ce_anomaly_monitor.service.arn],
    aws_ce_anomaly_monitor.team[*].arn,
  )
}

resource "aws_ce_anomaly_subscription" "immediate" {
  name             = "${var.name_prefix}-anomalies-immediate"
  frequency        = "IMMEDIATE" # IMMEDIATE supports SNS subscribers only
  monitor_arn_list = local.monitor_arns

  subscriber {
    type    = "SNS"
    address = aws_sns_topic.alerts.arn
  }

  threshold_expression {
    or {
      dimension {
        key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
        match_options = ["GREATER_THAN_OR_EQUAL"]
        values        = [tostring(var.anomaly_threshold_usd)]
      }
    }
    or {
      dimension {
        key           = "ANOMALY_TOTAL_IMPACT_PERCENTAGE"
        match_options = ["GREATER_THAN_OR_EQUAL"]
        values        = [tostring(var.anomaly_threshold_percent)]
      }
    }
  }

  tags       = var.tags
  depends_on = [aws_sns_topic_policy.alerts]
}

resource "aws_ce_anomaly_subscription" "daily" {
  count            = length(var.notification_emails) > 0 ? 1 : 0
  name             = "${var.name_prefix}-anomalies-daily"
  frequency        = "DAILY"
  monitor_arn_list = local.monitor_arns

  dynamic "subscriber" {
    for_each = toset(var.notification_emails)
    content {
      type    = "EMAIL"
      address = subscriber.value
    }
  }

  threshold_expression {
    dimension {
      key           = "ANOMALY_TOTAL_IMPACT_ABSOLUTE"
      match_options = ["GREATER_THAN_OR_EQUAL"]
      values        = [tostring(var.anomaly_threshold_usd)]
    }
  }

  tags = var.tags
}

# ----------------------------------------------------------------------------- cost allocation tags
resource "aws_ce_cost_allocation_tag" "required" {
  for_each = var.activate_cost_allocation_tags ? toset(var.required_tags) : toset([])
  tag_key  = each.value
  status   = "Active"
}

# ----------------------------------------------------------------------------- FOCUS export bucket
resource "aws_s3_bucket" "exports" {
  count  = var.enable_data_export ? 1 : 0
  bucket = local.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "exports" {
  count                   = var.enable_data_export ? 1 : 0
  bucket                  = aws_s3_bucket.exports[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "exports" {
  count  = var.enable_data_export ? 1 : 0
  bucket = aws_s3_bucket.exports[0].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "exports" {
  count  = var.enable_data_export ? 1 : 0
  bucket = aws_s3_bucket.exports[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "exports" {
  count  = var.enable_data_export ? 1 : 0
  bucket = aws_s3_bucket.exports[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.finops.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "exports" {
  count  = var.enable_data_export ? 1 : 0
  bucket = aws_s3_bucket.exports[0].id

  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.export_retention_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "exports" {
  count = var.enable_data_export ? 1 : 0

  statement {
    sid     = "BillingExportsWrite"
    actions = ["s3:PutObject", "s3:GetBucketPolicy"]
    resources = [
      aws_s3_bucket.exports[0].arn,
      "${aws_s3_bucket.exports[0].arn}/*",
    ]
    principals {
      type        = "Service"
      identifiers = ["bcm-data-exports.amazonaws.com", "billingreports.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
    condition {
      test     = "StringLike"
      variable = "aws:SourceArn"
      values = [
        "arn:${local.partition}:cur:us-east-1:${local.account_id}:definition/*",
        "arn:${local.partition}:bcm-data-exports:us-east-1:${local.account_id}:export/*",
      ]
    }
  }

  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.exports[0].arn, "${aws_s3_bucket.exports[0].arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "exports" {
  count  = var.enable_data_export ? 1 : 0
  bucket = aws_s3_bucket.exports[0].id
  policy = data.aws_iam_policy_document.exports[0].json

  depends_on = [aws_s3_bucket_public_access_block.exports]
}

# ----------------------------------------------------------------------------- FOCUS data export (CUR 2.0)
resource "aws_bcmdataexports_export" "focus" {
  count = var.enable_data_export ? 1 : 0

  export {
    name        = "${var.name_prefix}-focus"
    description = "FOCUS 1.0 cost and usage for golden.finops showback, anomalies and recommendations."

    data_query {
      query_statement      = "SELECT ${join(", ", var.focus_columns)} FROM ${var.focus_table}"
      table_configurations = { (var.focus_table) = {} }
    }

    destination_configurations {
      s3_destination {
        s3_bucket = aws_s3_bucket.exports[0].id
        s3_prefix = var.export_prefix
        s3_region = local.region

        s3_output_configurations {
          overwrite   = "OVERWRITE_REPORT"
          format      = "PARQUET"
          compression = "PARQUET"
          output_type = "CUSTOM"
        }
      }
    }

    refresh_cadence {
      frequency = "SYNCHRONOUS"
    }
  }

  tags       = var.tags
  depends_on = [aws_s3_bucket_policy.exports]
}
