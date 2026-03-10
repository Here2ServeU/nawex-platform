# ------------------------------------------------------------------------------
# BOOTSTRAP VARIABLES
# ------------------------------------------------------------------------------

variable "location" {
  description = "Azure Region for the State Store"
  type        = string
  default     = "eastus2"
}

variable "tags" {
  description = "Governance Tags"
  type        = map(string)
  default = {
    Project     = "Express Web"
    Environment = "Management"
    Owner       = "PlatformEngineering"
    ManagedBy   = "Terraform-Bootstrap"
  }
}
