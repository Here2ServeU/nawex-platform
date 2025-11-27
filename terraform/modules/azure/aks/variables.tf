# ------------------------------------------------------------------------------
# EXPRESS WEB AWS DEV VARIABLES
# ------------------------------------------------------------------------------

variable "tags" {
  description = "Global Tags"
  type        = map(string)
  default = {
    Project     = "Express Web"
    Environment = "Dev"
    CostCenter  = "Dev-101"
    ManagedBy   = "Terraform"
  }
}
