variable "name_prefix" {
  description = "Prefix for budget, topic and dataset names, e.g. golden -> golden-monthly."
  type        = string
  default     = "golden"
}

variable "billing_account" {
  description = "Cloud Billing account ID (XXXXXX-XXXXXX-XXXXXX). The caller needs Billing Account Costs Manager on it."
  type        = string
}

variable "project_id" {
  description = "Project that hosts the Pub/Sub topic and BigQuery dataset, and whose spend the project budget covers."
  type        = string
}

variable "budget_project_ids" {
  description = "Projects covered by the main budget. Empty = only project_id."
  type        = list(string)
  default     = []
}

variable "required_labels" {
  description = "Labels every resource must carry (GCP label keys are lowercase snake_case). Enforced by security/policies/opa/tagging.rego."
  type        = list(string)
  default     = ["project", "environment", "team", "cost_center", "owner"]
}

variable "team_label_key" {
  description = "Label key that identifies the owning team; per-team budgets filter on it."
  type        = string
  default     = "team"
}

variable "currency" {
  description = "Budget currency; must match the billing account currency."
  type        = string
  default     = "USD"
}

variable "monthly_budget" {
  description = "Monthly budget for budget_project_ids, in whole currency units."
  type        = number
  default     = 5000
}

variable "team_budgets" {
  description = "Team label value -> monthly budget (whole units), filtered on <team_label_key>=<team>."
  type        = map(number)
  default     = {}
}

variable "actual_thresholds" {
  description = "Fractions of the budget that alert on current spend (0.5 = 50%)."
  type        = list(number)
  default     = [0.5, 0.8, 1.0]
}

variable "forecast_thresholds" {
  description = "Fractions of the budget that alert on forecasted spend."
  type        = list(number)
  default     = [1.0]
}

variable "monitoring_notification_channels" {
  description = "Cloud Monitoring notification channel IDs (email, Slack, PagerDuty) for budget alerts. Max 5."
  type        = list(string)
  default     = []
}

variable "disable_default_iam_recipients" {
  description = "Stop emailing billing admins/users by default (set true once notification channels are wired)."
  type        = bool
  default     = false
}

variable "enable_billing_export_dataset" {
  description = "Create the BigQuery dataset that Cloud Billing exports into (the export itself is enabled in the console)."
  type        = bool
  default     = true
}

variable "dataset_location" {
  description = "BigQuery dataset location. Use a multi-region (US/EU) to get backfilled billing data."
  type        = string
  default     = "US"
}

variable "kms_key_name" {
  description = "Optional Cloud KMS key for the Pub/Sub topic and BigQuery dataset. Empty = Google-managed encryption."
  type        = string
  default     = ""
}

variable "labels" {
  description = "Labels applied to the topic and dataset (should include every required label)."
  type        = map(string)
  default     = {}
}
