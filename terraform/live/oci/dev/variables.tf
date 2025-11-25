variable "region" {
  description = "OCI region."
  type        = string
  default     = "us-ashburn-1"
}

variable "compartment_id" {
  description = "Compartment OCID."
  type        = string
}

variable "vcn_id" {
  description = "VCN OCID."
  type        = string
}
