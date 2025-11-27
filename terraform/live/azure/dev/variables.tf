# ------------------------------------------------------------------------------
# Purpose: strict typing for Azure deployment parameters.
# ------------------------------------------------------------------------------

variable "location" {
  description = "The Azure Region for the Control Plane."
  type        = string
  default     = "eastus2"
  validation {
    condition     = contains(["eastus2", "westeurope", "southeastasia"], var.location)
    error_message = "Deployment restricted to regions with 3 Availability Zones for 99.99% SLA."
  }
}

variable "tags" {
  description = "Global Governance Tags."
  type        = map(string)
  default = {
    Project     = "Nexus"
    Environment = "Production"
    Cloud       = "Azure"
    Owner       = "PlatformEngineering"
    CostCenter  = "AI-Infrastructure-101"
    Compliance  = "SOC2-TypeII"
  }
}

variable "k8s_version" {
  description = "Kubernetes Version (Must align with Control Plane)."
  type        = string
  default     = "1.29"
}

variable "sku_tier" {
  description = "The SLA tier for the control plane."
  type        = string
  default     = "Standard" # Costs ~$73/mo but provides financial SLA
}
