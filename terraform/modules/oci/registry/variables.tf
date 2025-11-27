variable "tenancy_ocid" {}
variable "user_ocid" {}
variable "fingerprint" {}
variable "private_key_path" {}
variable "region" {}
variable "compartment_id" {}

variable "tags" {
  default = {
    Project = "Express Web"
    Role    = "ArtifactStore"
  }
}
