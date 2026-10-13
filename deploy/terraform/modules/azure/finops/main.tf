# ------------------------------------------------------------------------------
# AZURE FINOPS MODULE (Consumption budgets + Cost Management export)
# ------------------------------------------------------------------------------
# Description: The Azure half of the FinOps "Inform" and "Operate" layers.
#
#   Budgets   subscription budget, per-team budgets (subscription scope filtered
#             on the team tag) and optional per-resource-group budgets; actual
#             and forecasted notifications to email and action groups
#   Export    daily month-to-date AmortizedCost export into a private, TLS 1.2,
#             versioned storage container. Cost Management can also emit the
#             FOCUS dataset ("FocusCost") from the portal/API; azurerm 3.x
#             only models ActualCost/AmortizedCost/Usage, and golden.finops
#             maps the amortized columns onto FOCUS (CostInBillingCurrency ->
#             EffectiveCost, MeterCategory -> ServiceName, ...).
#
# Required tags are enforced at plan time by security/policies/opa/tagging.rego
# and at runtime by the built-in Azure Policy "Require a tag on resources"
# (assign once per required tag at the management group). Azure has no
# provider-level default tags: every resource must set them explicitly.
# See docs/finops/README.md.
# ------------------------------------------------------------------------------

locals {
  scope = "/subscriptions/${var.subscription_id}"

  notifications = concat(
    [for t in var.actual_thresholds : { type = "Actual", threshold = t }],
    [for t in var.forecast_thresholds : { type = "Forecasted", threshold = t }],
  )

  export_enabled = var.enable_cost_export && var.export_storage_account_name != ""
}

# ----------------------------------------------------------------------------- budgets
resource "azurerm_consumption_budget_subscription" "monthly" {
  name            = "${var.name_prefix}-monthly"
  subscription_id = local.scope
  amount          = var.monthly_budget
  time_grain      = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  dynamic "notification" {
    for_each = local.notifications
    content {
      enabled        = true
      operator       = "GreaterThan"
      threshold      = notification.value.threshold
      threshold_type = notification.value.type
      contact_emails = var.notification_emails
      contact_groups = var.action_group_ids
    }
  }

  lifecycle {
    ignore_changes = [time_period] # start_date may not move once the budget exists
  }
}

resource "azurerm_consumption_budget_subscription" "team" {
  for_each        = var.team_budgets
  name            = "${var.name_prefix}-team-${lower(each.key)}"
  subscription_id = local.scope
  amount          = each.value
  time_grain      = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  filter {
    tag {
      name   = var.team_tag_key
      values = [each.key]
    }
  }

  dynamic "notification" {
    for_each = local.notifications
    content {
      enabled        = true
      operator       = "GreaterThan"
      threshold      = notification.value.threshold
      threshold_type = notification.value.type
      contact_emails = var.notification_emails
      contact_groups = var.action_group_ids
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

resource "azurerm_consumption_budget_resource_group" "this" {
  for_each          = var.resource_group_budgets
  name              = "${var.name_prefix}-rg-${element(split("/", each.key), length(split("/", each.key)) - 1)}"
  resource_group_id = each.key
  amount            = each.value
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  dynamic "notification" {
    for_each = local.notifications
    content {
      enabled        = true
      operator       = "GreaterThan"
      threshold      = notification.value.threshold
      threshold_type = notification.value.type
      contact_emails = var.notification_emails
      contact_groups = var.action_group_ids
    }
  }

  lifecycle {
    ignore_changes = [time_period]
  }
}

# ----------------------------------------------------------------------------- cost export
resource "azurerm_storage_account" "exports" {
  count                             = local.export_enabled ? 1 : 0
  name                              = var.export_storage_account_name
  resource_group_name               = var.export_resource_group_name
  location                          = var.location
  account_tier                      = "Standard"
  account_replication_type          = "ZRS"
  min_tls_version                   = "TLS1_2"
  https_traffic_only_enabled        = true
  allow_nested_items_to_be_public   = false
  infrastructure_encryption_enabled = true

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 30
    }
  }

  tags = var.tags
}

resource "azurerm_storage_container" "exports" {
  count                 = local.export_enabled ? 1 : 0
  name                  = "cost-exports"
  storage_account_name  = azurerm_storage_account.exports[0].name
  container_access_type = "private"
}

resource "azurerm_subscription_cost_management_export" "daily" {
  count                        = local.export_enabled ? 1 : 0
  name                         = "${var.name_prefix}-daily-${lower(var.export_type)}"
  subscription_id              = local.scope
  recurrence_type              = "Daily"
  recurrence_period_start_date = var.export_start_date
  recurrence_period_end_date   = var.export_end_date

  export_data_storage_location {
    container_id     = azurerm_storage_container.exports[0].resource_manager_id
    root_folder_path = "/${var.name_prefix}"
  }

  export_data_options {
    type       = var.export_type
    time_frame = "MonthToDate"
  }
}
