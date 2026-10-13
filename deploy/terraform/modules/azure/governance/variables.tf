variable "name_prefix" {
  description = "Prefix for management group IDs (e.g. golden → golden-platform)."
  type        = string
  default     = "golden"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,30}$", var.name_prefix))
    error_message = "name_prefix must be lowercase alphanumerics and dashes, at most 31 characters."
  }
}

variable "root_display_name" {
  description = "Display name of the intermediate root management group."
  type        = string
  default     = "Golden"
}

variable "parent_management_group_id" {
  description = "Parent of the intermediate root (/providers/Microsoft.Management/managementGroups/<tenant-id> for the tenant root group). Null = tenant root."
  type        = string
  default     = null
}

variable "subscription_placement" {
  description = "Subscription ID (GUID) -> management group key (platform, landing-zones-prod, landing-zones-nonprod, sandbox, decommissioned)."
  type        = map(string)
  default     = {}

  validation {
    condition = alltrue([
      for id, mg in var.subscription_placement :
      can(regex("^[0-9a-fA-F-]{36}$", id)) && contains(["root", "platform", "landing-zones", "landing-zones-prod", "landing-zones-nonprod", "sandbox", "decommissioned"], mg)
    ])
    error_message = "subscription_placement keys must be subscription GUIDs and values known management group keys."
  }
}

# ------------------------------------------------------------------------------ policy
variable "location" {
  description = "Region for the managed identities of deployIfNotExists policy assignments."
  type        = string
  default     = "eastus2"
}

variable "allowed_locations" {
  description = "Azure regions resources may be created in (Allowed locations policy)."
  type        = list(string)
  default     = ["eastus2", "centralus"]
}

variable "required_tags" {
  description = "Tags every resource must carry (one 'Require a tag on resources' assignment each)."
  type        = list(string)
  default     = ["Team", "CostCenter", "Environment"]
}

variable "enforce_policies" {
  description = "false = DoNotEnforce (audit-only rollout); true = deny / deployIfNotExists take effect."
  type        = bool
  default     = true
}

variable "policy_scope_overrides" {
  description = "Policy assignment key -> management group key, for staged rollout (e.g. deny-nic-public-ip = sandbox first)."
  type        = map(string)
  default     = {}
}

variable "policy_definition_ids" {
  description = "Override built-in policy definition IDs (keyed like local.builtin_policies) if Microsoft re-versions one."
  type        = map(string)
  default     = {}
}

variable "defender_enabled" {
  description = "Assign the Defender for Cloud deployIfNotExists policy (needs a managed identity + role at root)."
  type        = bool
  default     = true
}

variable "defender_remediation_role" {
  description = "Built-in role granted to the Defender policy's managed identity; must match the definition's roleDefinitionIds."
  type        = string
  default     = "Security Admin"
}

variable "classic_resource_types" {
  description = "Classic (ASM) resource types denied by the 'Not allowed resource types' assignment."
  type        = list(string)
  default = [
    "Microsoft.ClassicCompute/virtualMachines",
    "Microsoft.ClassicCompute/domainNames",
    "Microsoft.ClassicStorage/storageAccounts",
    "Microsoft.ClassicNetwork/virtualNetworks",
    "Microsoft.ClassicNetwork/reservedIps",
    "Microsoft.ClassicNetwork/networkSecurityGroups",
  ]
}

# ------------------------------------------------------------------------------ identity
variable "identity_enabled" {
  description = "Manage persona role assignments / PIM from the access model."
  type        = bool
  default     = true
}

variable "access_model" {
  description = "Decoded security/identity/azure-access-model.yaml (yamldecode(file(...)))."
  type        = any
  default     = null

  validation {
    condition     = var.access_model == null || length(try(var.access_model.personas, [])) > 0
    error_message = "access_model must define personas."
  }
}

variable "pim_eligibility_days" {
  description = "Eligible assignments expire after this many days (PIM allows 15, 30, 90, 180 or 365)."
  type        = number
  default     = 365

  validation {
    condition     = contains([15, 30, 90, 180, 365], var.pim_eligibility_days)
    error_message = "pim_eligibility_days must be one of 15, 30, 90, 180, 365."
  }
}

variable "pim_approver_group" {
  description = "Display name of the Entra group that approves activations for personas with require_approval (looked up, never created)."
  type        = string
  default     = null
}
