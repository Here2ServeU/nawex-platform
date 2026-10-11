variable "tenancy_ocid" {}
variable "user_ocid" {}
variable "fingerprint" {}
variable "private_key_path" {}
variable "region" {}
variable "compartment_id" {}

variable "tags" {
  default = {
    Project = "golden"
    Role    = "ArtifactStore"
  }
}

variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
  default     = "golden"
}
