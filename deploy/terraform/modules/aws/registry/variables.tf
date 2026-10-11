variable "project" {
  description = "Repository name prefix."
  type        = string
  default     = "golden"
}

variable "images" {
  description = "Image names to create repositories for."
  type        = list(string)
  default     = ["golden-platform", "golden-client-portal", "golden-workload"]
}

variable "immutable_tags" {
  type    = bool
  default = true
}

variable "force_delete" {
  description = "Allow deleting repositories that still contain images."
  type        = bool
  default     = false
}

variable "keep_images" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
