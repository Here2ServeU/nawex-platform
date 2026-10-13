variable "wiz_principal_arn" {
  description = "Wiz-provided AWS principal ARN that assumes the connector role (from the Wiz connector wizard)."
  type        = string

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:iam::[0-9]{12}:(role|root)", var.wiz_principal_arn))
    error_message = "wiz_principal_arn must be an IAM role or account-root ARN."
  }
}

variable "external_id" {
  description = "Wiz tenant external ID (sts:ExternalId)."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.external_id) >= 16
    error_message = "external_id must be at least 16 characters."
  }
}

variable "role_name" {
  description = "Connector role name."
  type        = string
  default     = "WizAccess-Role"
}

variable "permissions_boundary_arn" {
  description = "Workload permission boundary ARN (modules/aws/permission-boundary)."
  type        = string
}

variable "tags" {
  description = "Tags applied to the role."
  type        = map(string)
  default     = {}
}
