variable "name_prefix" {
  description = "Prefix for budget, monitor, topic, bucket and export names, e.g. golden -> golden-monthly."
  type        = string
  default     = "golden"
}

variable "required_tags" {
  description = "Cost allocation tags every resource must carry. Activated in Billing and enforced by security/policies/opa/tagging.rego."
  type        = list(string)
  default     = ["Project", "Environment", "Team", "CostCenter", "Owner"]
}

variable "activate_cost_allocation_tags" {
  description = "Activate required_tags as user-defined cost allocation tags. Run in the management (payer) account; a tag can only be activated after it has appeared on a billed resource."
  type        = bool
  default     = true
}

variable "team_tag_key" {
  description = "Tag key that identifies the owning team. Drives the per-team budgets and the tag anomaly monitor."
  type        = string
  default     = "Team"
}

variable "currency" {
  description = "Budget currency (AWS Budgets supports USD for cost budgets)."
  type        = string
  default     = "USD"
}

variable "monthly_budget" {
  description = "Monthly cost budget for the whole account (or consolidated billing family when run in the payer account)."
  type        = number
  default     = 5000
}

variable "linked_account_budgets" {
  description = "Member account ID -> monthly budget. Only meaningful in the payer account; leave empty in a member account."
  type        = map(number)
  default     = {}
}

variable "team_budgets" {
  description = "Team tag value -> monthly budget, filtered on user:<team_tag_key>$<team>."
  type        = map(number)
  default     = {}
}

variable "actual_thresholds" {
  description = "Percent-of-budget thresholds that alert on ACTUAL spend."
  type        = list(number)
  default     = [50, 80, 100]
}

variable "forecast_thresholds" {
  description = "Percent-of-budget thresholds that alert on FORECASTED end-of-month spend."
  type        = list(number)
  default     = [100]
}

variable "notification_emails" {
  description = "Email addresses notified by budgets and the daily anomaly digest."
  type        = list(string)
  default     = []
}

variable "anomaly_threshold_usd" {
  description = "Minimum absolute impact (USD) before a cost anomaly is sent to subscribers."
  type        = number
  default     = 100
}

variable "anomaly_threshold_percent" {
  description = "Minimum impact as a percent of expected spend; an anomaly alerts when EITHER threshold is crossed."
  type        = number
  default     = 20
}

variable "anomaly_monitor_teams" {
  description = "Team tag values watched by the cost-allocation-tag anomaly monitor. Empty = keys of team_budgets."
  type        = list(string)
  default     = []
}

variable "enable_data_export" {
  description = "Create the FOCUS 1.0 Data Export (CUR 2.0 family) and its S3 bucket. Data Exports is a us-east-1 API, so the calling provider must be us-east-1."
  type        = bool
  default     = true
}

variable "export_bucket_name" {
  description = "S3 bucket for billing exports. Empty = <name_prefix>-billing-exports-<account id>."
  type        = string
  default     = ""
}

variable "export_prefix" {
  description = "Key prefix for export objects inside the bucket."
  type        = string
  default     = "focus"
}

variable "export_retention_days" {
  description = "Days to keep noncurrent export object versions."
  type        = number
  default     = 90
}

variable "focus_table" {
  description = "Data Exports table to query. FOCUS_1_0_AWS is the FOCUS 1.0 view of CUR 2.0."
  type        = string
  default     = "FOCUS_1_0_AWS"
}

variable "focus_columns" {
  description = "FOCUS columns selected by the export. Defaults to the columns golden.finops.focus reads plus the common billing dimensions."
  type        = list(string)
  default = [
    "AvailabilityZone", "BilledCost", "BillingAccountId", "BillingCurrency", "BillingPeriodEnd",
    "BillingPeriodStart", "ChargeCategory", "ChargeDescription", "ChargeFrequency", "ChargePeriodEnd",
    "ChargePeriodStart", "CommitmentDiscountCategory", "CommitmentDiscountId", "CommitmentDiscountType",
    "ConsumedQuantity", "ConsumedUnit", "EffectiveCost", "ListCost", "ListUnitPrice", "PricingCategory",
    "PricingQuantity", "PricingUnit", "ProviderName", "PublisherName", "RegionId", "RegionName",
    "ResourceId", "ResourceName", "ResourceType", "ServiceCategory", "ServiceName", "SkuId", "SkuPriceId",
    "SubAccountId", "SubAccountName", "Tags",
  ]
}

variable "tags" {
  description = "Tags applied to every taggable resource in this module (merged with provider default_tags)."
  type        = map(string)
  default     = {}
}
