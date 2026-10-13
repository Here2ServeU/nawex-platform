variable "access_model" {
  description = "Decoded security/identity/access-model.yaml (yamldecode(file(...)))."
  type        = any

  validation {
    condition     = length(try(var.access_model.personas, [])) > 0 && try(var.access_model.permission_boundary, "") != ""
    error_message = "access_model must define personas and permission_boundary."
  }
}

variable "account_groups" {
  description = "Logical account group (as used in the access model) -> list of 12-digit account IDs."
  type        = map(list(string))

  validation {
    condition     = alltrue([for ids in values(var.account_groups) : alltrue([for id in ids : can(regex("^[0-9]{12}$", id))])])
    error_message = "account_groups values must be 12-digit AWS account IDs."
  }
}

variable "tags" {
  description = "Tags applied to permission sets."
  type        = map(string)
  default     = {}
}
