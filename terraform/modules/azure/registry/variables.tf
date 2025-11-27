# ------------------------------------------------------------------------------
# REGISTRY VARIABLES
# ------------------------------------------------------------------------------

variable "location" {
  description = "Azure Region for the Registry"
  type        = string
  default     = "eastus2"
}

variable "tags" {
  description = "Governance Tags"
  type        = map(string)
  default = {
    Project     = "Express Web"
    Environment = "Shared-Services" # Distinct from 'Dev' or 'Prod'
    Owner       = "PlatformEngineering"
    ManagedBy   = "Terraform"
    CostCenter  = "Shared-101"
  }
}
