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

variable "allowed_ips" {
  description = "Public IPs / CIDRs (operator workstation, CI runner egress) allowed to reach the state storage account. Everything else is denied."
  type        = list(string)
  default     = []
}
