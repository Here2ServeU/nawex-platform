variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "Region for the bucket"
  type        = string
  default     = "us-central1"
}

variable "labels" {
  type = map(string)
  default = {
    managed_by = "terraform-bootstrap"
    owner      = "platform-engineering"
  }
}

variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
  default     = "golden"
}
