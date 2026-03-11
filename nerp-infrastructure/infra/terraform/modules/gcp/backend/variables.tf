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
