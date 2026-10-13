variable "name_prefix" {
  description = "Prefix for budget and export names, e.g. golden -> golden-monthly."
  type        = string
  default     = "golden"
}

variable "subscription_id" {
  description = "Subscription GUID the budgets and export cover (without the /subscriptions/ prefix)."
  type        = string
}

variable "required_tags" {
  description = "Tags every resource must carry. Enforced at plan time by security/policies/opa/tagging.rego and at runtime by Azure Policy (see docs/finops/README.md)."
  type        = list(string)
  default     = ["Project", "Environment", "Team", "CostCenter", "Owner"]
}

variable "team_tag_key" {
  description = "Tag key that identifies the owning team; per-team budgets filter on it."
  type        = string
  default     = "Team"
}

variable "monthly_budget" {
  description = "Monthly cost budget for the subscription, in the billing currency."
  type        = number
  default     = 5000
}

variable "team_budgets" {
  description = "Team tag value -> monthly budget. Each becomes a subscription budget filtered on <team_tag_key> = <team>."
  type        = map(number)
  default     = {}
}

variable "resource_group_budgets" {
  description = "Resource group ID -> monthly budget, for teams that own whole resource groups."
  type        = map(number)
  default     = {}
}

variable "budget_start_date" {
  description = "First day of the budget period (RFC3339, first of a month, not in the past at creation), e.g. 2026-11-01T00:00:00Z."
  type        = string
}

variable "actual_thresholds" {
  description = "Percent-of-budget thresholds that alert on actual spend."
  type        = list(number)
  default     = [50, 80, 100]
}

variable "forecast_thresholds" {
  description = "Percent-of-budget thresholds that alert on forecasted spend."
  type        = list(number)
  default     = [100]
}

variable "notification_emails" {
  description = "Email addresses notified when a budget threshold is crossed."
  type        = list(string)
  default     = []
}

variable "action_group_ids" {
  description = "Azure Monitor action group IDs (ChatOps, PagerDuty) notified alongside the emails."
  type        = list(string)
  default     = []
}

variable "enable_cost_export" {
  description = "Create a storage account + container and a daily month-to-date amortized cost export."
  type        = bool
  default     = true
}

variable "export_resource_group_name" {
  description = "Resource group for the export storage account (required when enable_cost_export = true)."
  type        = string
  default     = ""
}

variable "location" {
  description = "Region for the export storage account."
  type        = string
  default     = "eastus"
}

variable "export_storage_account_name" {
  description = "Globally unique storage account name (3-24 lowercase alphanumerics) for cost exports."
  type        = string
  default     = ""
}

variable "export_type" {
  description = "Cost Management export dataset: ActualCost, AmortizedCost or Usage. AmortizedCost spreads reservations/savings plans and matches FOCUS EffectiveCost."
  type        = string
  default     = "AmortizedCost"

  validation {
    condition     = contains(["ActualCost", "AmortizedCost", "Usage"], var.export_type)
    error_message = "export_type must be ActualCost, AmortizedCost or Usage."
  }
}

variable "export_start_date" {
  description = "Export recurrence start (RFC3339)."
  type        = string
  default     = "2026-11-01T00:00:00Z"
}

variable "export_end_date" {
  description = "Export recurrence end (RFC3339)."
  type        = string
  default     = "2031-12-31T00:00:00Z"
}

variable "tags" {
  description = "Tags for the storage account (should include every required tag)."
  type        = map(string)
  default     = {}
}
