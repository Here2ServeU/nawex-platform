variable "accounts" {
  description = "Account name -> placement. account_group must be an account group of security/identity/access-model.yaml."
  type = map(object({
    email         = string
    ou_id         = string
    account_group = string
    tags          = optional(map(string), {})
  }))

  validation {
    condition = alltrue([
      for a in values(var.accounts) : can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", a.email)) && can(regex("^(r-[0-9a-z]{4,32}|ou-[0-9a-z]{4,32}-[a-z0-9]{8,32})$", a.ou_id))
    ])
    error_message = "Each account needs a valid email and an OU (ou-xxxx-xxxxxxxx) or root (r-xxxx) parent ID."
  }

  validation {
    condition     = length(distinct([for a in values(var.accounts) : lower(a.email)])) == length(var.accounts)
    error_message = "Account root emails must be unique."
  }

  validation {
    condition = alltrue([
      for a in values(var.accounts) : contains(["management", "security", "shared-services", "network", "workloads-prod", "workloads-nonprod", "sandbox"], a.account_group)
    ])
    error_message = "account_group must be one of the access model's account groups."
  }
}

variable "role_name" {
  description = "Cross-account admin role created in each new account for the management account (used for bootstrap, then guarded by SCPs)."
  type        = string
  default     = "OrganizationAccountAccessRole"
}

variable "iam_user_access_to_billing" {
  description = "Whether IAM principals in the account may see billing (ALLOW / DENY)."
  type        = string
  default     = "DENY"

  validation {
    condition     = contains(["ALLOW", "DENY"], var.iam_user_access_to_billing)
    error_message = "iam_user_access_to_billing must be ALLOW or DENY."
  }
}

variable "tags" {
  description = "Tags applied to every account."
  type        = map(string)
  default     = {}
}
