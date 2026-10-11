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
    Project     = "golden"
    Environment = "Management"
    Owner       = "PlatformEngineering"
    ManagedBy   = "Terraform-Bootstrap"
  }
}

variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
  default     = "golden"
}
