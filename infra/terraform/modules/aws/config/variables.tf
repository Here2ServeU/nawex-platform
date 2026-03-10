variable "name" {
  type        = string
  description = "Name prefix for AWS Config resources."
}

variable "bucket_name" {
  type        = string
  description = "S3 bucket for Config delivery channel."
}

variable "create_bucket" {
  type        = bool
  description = "Whether to create the S3 bucket for Config."
  default     = true
}

variable "include_global_resource_types" {
  type        = bool
  description = "Include global resource types in the recorder."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Tags applied to created resources."
  default     = {}
}
