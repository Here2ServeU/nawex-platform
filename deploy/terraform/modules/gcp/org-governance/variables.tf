variable "org_id" {
  description = "Numeric GCP organization ID."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.org_id))
    error_message = "org_id must be the numeric organization ID."
  }
}

variable "customer_id" {
  description = "Cloud Identity / Workspace directory customer ID (C0xxxxxxx) — the only domain allowed in IAM policies."
  type        = string

  validation {
    condition     = can(regex("^C[0-9a-z]+$", var.customer_id))
    error_message = "customer_id must look like C0xxxxxxx (gcloud organizations describe <org> --format='value(owner.directoryCustomerId)')."
  }
}

variable "folder_prefix" {
  description = "Prefix for folder display names (e.g. 'Golden' → 'Golden Platform')."
  type        = string
  default     = "Golden"
}

# ------------------------------------------------------------------------------ org policy
variable "allowed_locations" {
  description = "Values for constraints/gcp.resourceLocations (value groups such as in:us-locations, or regions)."
  type        = list(string)
  default     = ["in:us-locations"]
}

variable "org_policies_enabled" {
  description = "Manage the organization policy constraints."
  type        = bool
  default     = true
}

variable "dry_run_constraints" {
  description = "Constraints rolled out in dry-run (violations logged, not enforced) before enforcing."
  type        = list(string)
  default     = []
}

# ------------------------------------------------------------------------------ identity
variable "identity_enabled" {
  description = "Manage persona IAM bindings, PAM entitlements and the deny policy from the access model."
  type        = bool
  default     = true
}

variable "access_model" {
  description = "Decoded security/identity/gcp-access-model.yaml (yamldecode(file(...)))."
  type        = any
  default     = null

  validation {
    condition     = var.access_model == null || length(try(var.access_model.personas, [])) > 0
    error_message = "access_model must define personas."
  }
}

variable "domain" {
  description = "Cloud Identity primary domain substituted for $${domain} in group addresses (defaults to the model's identity_source.domain)."
  type        = string
  default     = null
}

variable "verify_groups" {
  description = "Look every persona group up in Cloud Identity so a group missing from GCDS fails the plan (needs cloudidentity.googleapis.com + a quota project)."
  type        = bool
  default     = true
}

variable "pam_location" {
  description = "Location for Privileged Access Manager entitlements."
  type        = string
  default     = "global"
}

variable "pam_approvers" {
  description = "Principals (group:… / user:…) who approve requests on entitlements with require_approval."
  type        = list(string)
  default     = []
}

variable "deny_policy_enabled" {
  description = "Attach the org-level IAM deny policy protecting security settings."
  type        = bool
  default     = true
}

variable "deny_exception_principals" {
  description = "Extra principals exempt from the deny policy, e.g. the Terraform deployer: principal://iam.googleapis.com/projects/-/serviceAccounts/<sa-email>."
  type        = list(string)
  default     = []
}

variable "denied_permissions" {
  description = "Permissions denied to everyone but break-glass and the deployer. Must be on Google's 'permissions supported in deny policies' list (v2 format service.googleapis.com/resource.verb)."
  type        = list(string)
  default = [
    "iam.googleapis.com/roles.create",
    "iam.googleapis.com/roles.update",
    "iam.googleapis.com/roles.delete",
    "iam.googleapis.com/serviceAccountKeys.create",
    "cloudresourcemanager.googleapis.com/projects.delete",
  ]
}
