variable "name_prefix" {
  description = "Prefix for policy names, e.g. golden -> golden-region-allowlist."
  type        = string
  default     = "golden"
}

variable "enabled_scps" {
  description = "SCP templates (policies/scp/<name>.json.tftpl) to create."
  type        = list(string)
  default = [
    "deny-root-and-iam-users",
    "enforce-permission-boundary",
    "protect-security-services",
    "region-allowlist",
  ]
}

variable "enabled_rcps" {
  description = "RCP templates (policies/rcp/<name>.json.tftpl) to create. RESOURCE_CONTROL_POLICY must be enabled on the org root."
  type        = list(string)
  default     = ["data-perimeter"]
}

variable "scp_targets" {
  description = "SCP name -> list of root / OU / account IDs to attach it to. Start with sandbox OUs."
  type        = map(list(string))
  default     = {}
}

variable "rcp_targets" {
  description = "RCP name -> list of root / OU / account IDs to attach it to."
  type        = map(list(string))
  default     = {}
}

variable "allowed_regions" {
  description = "Regions where regional services may be used (region-allowlist SCP)."
  type        = list(string)
  default     = ["us-east-1", "us-west-2"]
}

variable "boundary_policy_name" {
  description = "Name of the permission boundary every role must carry (modules/aws/permission-boundary)."
  type        = string
  default     = "golden-workload-boundary"
}

variable "exempt_principal_arns" {
  description = "Principal ARN patterns exempt from the guardrails: break-glass and the IaC deployer role. Keep this list short."
  type        = list(string)
  default = [
    "arn:*:iam::*:role/aws-reserved/sso.amazonaws.com/*AWSReservedSSO_BreakGlassAdmin_*",
    "arn:*:iam::*:role/golden-terraform-deployer",
  ]

  validation {
    condition     = length(var.exempt_principal_arns) > 0 && !contains(var.exempt_principal_arns, "*")
    error_message = "exempt_principal_arns must be a non-empty list of explicit ARN patterns (never \"*\")."
  }
}

variable "tags" {
  description = "Tags applied to every policy."
  type        = map(string)
  default     = {}
}
