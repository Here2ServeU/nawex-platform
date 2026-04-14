# ------------------------------------------------------------------------------
# EXPRESS WEB AZURE DEV VARIABLES
# ------------------------------------------------------------------------------

variable "location" {
  description = "Azure Region"
  type        = string
  default     = "eastus2" # Typically cheaper than West US
}

variable "tags" {
  description = "Governance Tags"
  type        = map(string)
  default = {
    Project     = "Express Web"
    Environment = "Dev"
    Owner       = "AppTeam"
    CostCenter  = "Dev-101"
    ManagedBy   = "Terraform"
  }
}
