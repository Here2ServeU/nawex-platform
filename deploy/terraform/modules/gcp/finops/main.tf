# ------------------------------------------------------------------------------
# GCP FINOPS MODULE (Cloud Billing budgets + Pub/Sub + BigQuery billing export)
# ------------------------------------------------------------------------------
# Description: The GCP half of the FinOps "Inform" and "Operate" layers.
#
#   Budgets   project budget and per-team budgets (label filter) with current
#             and forecasted threshold rules; every update is published to a
#             Pub/Sub topic so automation (ChatOps, golden.finops, a capping
#             Cloud Function for sandboxes) can react, plus optional Cloud
#             Monitoring notification channels
#   Export    BigQuery dataset for the Cloud Billing detailed usage cost
#             export. Cloud Billing exports cannot be enabled through an API:
#             after apply, open Billing > Billing export > BigQuery export and
#             select this dataset for "Detailed usage cost" (and "Pricing").
#             Google publishes a FOCUS BigQuery view over that export;
#             golden.finops reads either the FOCUS view or the raw export.
#
# Labels are enforced at plan time by security/policies/opa/tagging.rego and can
# be backed at runtime by an org policy custom constraint on resource labels.
# google provider >= 5 supports provider-level default_labels, which land in
# effective_labels and count towards the OPA check. See docs/finops/README.md.
# ------------------------------------------------------------------------------

data "google_project" "this" {
  project_id = var.project_id
}

data "google_project" "budget" {
  for_each   = toset(length(var.budget_project_ids) > 0 ? var.budget_project_ids : [var.project_id])
  project_id = each.value
}

locals {
  budget_projects = [for p in data.google_project.budget : "projects/${p.number}"]

  threshold_rules = concat(
    [for t in var.actual_thresholds : { percent = t, basis = "CURRENT_SPEND" }],
    [for t in var.forecast_thresholds : { percent = t, basis = "FORECASTED_SPEND" }],
  )
}

# ----------------------------------------------------------------------------- notifications
resource "google_pubsub_topic" "budget_alerts" {
  project      = var.project_id
  name         = "${var.name_prefix}-budget-alerts"
  kms_key_name = var.kms_key_name != "" ? var.kms_key_name : null
  labels       = var.labels
}

# Cloud Billing publishes budget notifications as this Google-owned service account.
resource "google_pubsub_topic_iam_member" "billing_publisher" {
  project = var.project_id
  topic   = google_pubsub_topic.budget_alerts.name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:billing-budget-alert@system.gserviceaccount.com"
}

# ----------------------------------------------------------------------------- budgets
resource "google_billing_budget" "monthly" {
  billing_account = var.billing_account
  display_name    = "${var.name_prefix}-monthly"

  budget_filter {
    projects        = local.budget_projects
    calendar_period = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = var.currency
      units         = tostring(floor(var.monthly_budget))
    }
  }

  dynamic "threshold_rules" {
    for_each = local.threshold_rules
    content {
      threshold_percent = threshold_rules.value.percent
      spend_basis       = threshold_rules.value.basis
    }
  }

  all_updates_rule {
    pubsub_topic                     = google_pubsub_topic.budget_alerts.id
    schema_version                   = "1.0"
    monitoring_notification_channels = var.monitoring_notification_channels
    disable_default_iam_recipients   = var.disable_default_iam_recipients
  }

  depends_on = [google_pubsub_topic_iam_member.billing_publisher]
}

resource "google_billing_budget" "team" {
  for_each        = var.team_budgets
  billing_account = var.billing_account
  display_name    = "${var.name_prefix}-team-${lower(each.key)}"

  # A budget label filter accepts one key with one value.
  budget_filter {
    projects        = local.budget_projects
    labels          = { (var.team_label_key) = each.key }
    calendar_period = "MONTH"
  }

  amount {
    specified_amount {
      currency_code = var.currency
      units         = tostring(floor(each.value))
    }
  }

  dynamic "threshold_rules" {
    for_each = local.threshold_rules
    content {
      threshold_percent = threshold_rules.value.percent
      spend_basis       = threshold_rules.value.basis
    }
  }

  all_updates_rule {
    pubsub_topic                     = google_pubsub_topic.budget_alerts.id
    schema_version                   = "1.0"
    monitoring_notification_channels = var.monitoring_notification_channels
    disable_default_iam_recipients   = var.disable_default_iam_recipients
  }

  depends_on = [google_pubsub_topic_iam_member.billing_publisher]
}

# ----------------------------------------------------------------------------- billing export dataset
resource "google_bigquery_dataset" "billing_export" {
  count                      = var.enable_billing_export_dataset ? 1 : 0
  project                    = var.project_id
  dataset_id                 = replace("${var.name_prefix}_billing_export", "-", "_")
  friendly_name              = "Cloud Billing export (${var.name_prefix})"
  description                = "Detailed usage cost + pricing export from Cloud Billing; source for FOCUS views and golden.finops."
  location                   = var.dataset_location
  delete_contents_on_destroy = false
  labels                     = var.labels

  dynamic "default_encryption_configuration" {
    for_each = var.kms_key_name != "" ? [var.kms_key_name] : []
    content {
      kms_key_name = default_encryption_configuration.value
    }
  }
}
