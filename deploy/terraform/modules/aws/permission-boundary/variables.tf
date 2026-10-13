variable "name" {
  description = "Boundary policy name. Must match `permission_boundary` in security/identity/access-model.yaml."
  type        = string
  default     = "golden-workload-boundary"
}

variable "path" {
  description = "IAM path for the boundary policy."
  type        = string
  default     = "/"
}

variable "tags" {
  description = "Tags applied to the policy."
  type        = map(string)
  default     = {}
}
