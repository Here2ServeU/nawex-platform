# ------------------------------------------------------------------------------
# EXPRESS WEB OCI VARIABLES
# ------------------------------------------------------------------------------
# Purpose: Parameters for the Oracle Cloud deployment.
# ------------------------------------------------------------------------------

# --- Authentication (Standard OCI) ---
variable "tenancy_ocid" {}
variable "user_ocid" {}
variable "fingerprint" {}
variable "private_key_path" {}

variable "region" {
  description = "OCI Region"
  type        = string
  default     = "us-ashburn-1" # Major OCI Hub
}

variable "compartment_id" {
  description = "The OCID of the Dev Compartment (Isolation Boundary)."
  type        = string
}

# --- Governance ---
variable "defined_tags" {
  description = "OCI Defined Tags for Cost Tracking (Namespace.Key = Value)"
  type        = map(string)
  default = {
    "Operations.Environment" = "Dev"
    "Operations.CostCenter"  = "Dev-101"
    "Operations.Project"     = "ExpressWeb"
  }
}
