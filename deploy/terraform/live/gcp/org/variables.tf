variable "org_id" {
  description = "Numeric organization ID."
  type        = string
}

variable "customer_id" {
  description = "Directory customer ID (C0xxxxxxx) allowed by iam.allowedPolicyMemberDomains."
  type        = string
}

variable "quota_project" {
  description = "Project billed for Cloud Identity / org-level API calls."
  type        = string
}

variable "folder_prefix" {
  description = "Prefix for folder display names."
  type        = string
  default     = "Golden"
}

variable "domain" {
  description = "Cloud Identity domain substituted into group addresses; null = model's identity_source.domain."
  type        = string
  default     = null
}

variable "allowed_locations" {
  description = "constraints/gcp.resourceLocations values."
  type        = list(string)
  default     = ["in:us-locations"]
}

variable "org_policies_enabled" {
  description = "Manage organization policy constraints."
  type        = bool
  default     = true
}

variable "dry_run_constraints" {
  description = "Constraints set in dry-run mode during rollout."
  type        = list(string)
  default     = []
}

variable "identity_enabled" {
  description = "Manage persona IAM, PAM entitlements and the deny policy."
  type        = bool
  default     = true
}

variable "verify_groups" {
  description = "Fail the plan if a persona group is missing from Cloud Identity."
  type        = bool
  default     = true
}

variable "pam_approvers" {
  description = "Approvers for break-glass PAM requests (group:… / user:…)."
  type        = list(string)
  default     = []
}

variable "deny_policy_enabled" {
  description = "Attach the org-level IAM deny policy."
  type        = bool
  default     = true
}

variable "deny_exception_principals" {
  description = "Principals besides break-glass exempt from the deny policy (the Terraform deployer SA)."
  type        = list(string)
  default     = []
}
