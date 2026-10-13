variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "golden"
}

variable "region" {
  description = "Home region of the management / Identity Center account."
  type        = string
  default     = "us-east-1"
}

variable "allowed_regions" {
  description = "Regions where regional services may be used (region-allowlist SCP)."
  type        = list(string)
  default     = ["us-east-1", "us-west-2"]
}

variable "exempt_principal_arns" {
  description = "Principal ARN patterns exempt from the guardrails (break-glass permission set, IaC deployer)."
  type        = list(string)
  default = [
    "arn:*:iam::*:role/aws-reserved/sso.amazonaws.com/*AWSReservedSSO_BreakGlassAdmin_*",
    "arn:*:iam::*:role/golden-terraform-deployer",
  ]
}

variable "scp_targets" {
  description = "SCP name -> root / OU / account IDs. Roll out sandbox -> nonprod -> prod."
  type        = map(list(string))
  default     = {}
}

variable "rcp_targets" {
  description = "RCP name -> root / OU / account IDs."
  type        = map(list(string))
  default     = {}
}

variable "identity_center_enabled" {
  description = "Manage IAM Identity Center permission sets and assignments from the access model."
  type        = bool
  default     = true
}

variable "account_groups" {
  description = "Access-model account group -> 12-digit account IDs."
  type        = map(list(string))
  default     = {}
}

variable "tags" {
  description = "Extra tags merged into every resource."
  type        = map(string)
  default     = {}
}
