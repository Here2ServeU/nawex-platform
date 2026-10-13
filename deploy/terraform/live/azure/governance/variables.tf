variable "project" {
  description = "Management group ID prefix."
  type        = string
  default     = "golden"
}

variable "root_display_name" {
  description = "Display name of the intermediate root management group."
  type        = string
  default     = "Golden"
}

variable "parent_management_group_id" {
  description = "Parent of the intermediate root; null = tenant root group."
  type        = string
  default     = null
}

variable "subscription_placement" {
  description = "Subscription GUID -> management group key."
  type        = map(string)
  default     = {}
}

variable "location" {
  description = "Region for deployIfNotExists managed identities."
  type        = string
  default     = "eastus2"
}

variable "allowed_locations" {
  description = "Approved Azure regions."
  type        = list(string)
  default     = ["eastus2", "centralus"]
}

variable "required_tags" {
  description = "Tags every resource must carry."
  type        = list(string)
  default     = ["Team", "CostCenter", "Environment"]
}

variable "enforce_policies" {
  description = "false = audit-only (DoNotEnforce) rollout."
  type        = bool
  default     = true
}

variable "policy_scope_overrides" {
  description = "Policy assignment name -> management group key (staged rollout: sandbox -> nonprod -> prod)."
  type        = map(string)
  default     = {}
}

variable "defender_enabled" {
  description = "Assign the Defender for Cloud deployIfNotExists policy."
  type        = bool
  default     = true
}

variable "identity_enabled" {
  description = "Manage persona role assignments and PIM from the access model."
  type        = bool
  default     = true
}

variable "pim_approver_group" {
  description = "Entra group (display name) that approves break-glass activations."
  type        = string
  default     = "AZ-PIM-Approvers"
}
