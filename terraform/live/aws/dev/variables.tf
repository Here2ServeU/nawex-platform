# ------------------------------------------------------------------------------
# Purpose: Defines the configurable parameters for the Production environment.
# Strategy: Defaults are set to "Production" standards (us-east-1, strict tagging).
# ------------------------------------------------------------------------------

variable "region" {
  description = "The AWS Region to deploy the Nexus Control Plane into."
  type        = string
  default     = "us-east-1"
  validation {
    condition     = can(regex("^(us-east-1|us-west-2|eu-central-1)$", var.region))
    error_message = "Nexus Production is only certified for High-Availability regions (us-east-1, us-west-2, eu-central-1)."
  }
}

variable "tags" {
  description = "Global Resource Tags for FinOps and Governance."
  type        = map(string)
  default = {
    Project     = "Nexus"
    Environment = "Production"
    Owner       = "PlatformEngineering"
    ManagedBy   = "Terraform"
    CostCenter  = "AI-Infrastructure-101" # Critical for billing allocation
    Compliance  = "SOC2-TypeII"           # Critical for audit queries
  }
}

variable "cluster_version" {
  description = "The Kubernetes version for the EKS Control Plane."
  type        = string
  default     = "1.29"
}

# Principal Note: We do not pass sensitive values (DB passwords) here.
# Those are injected via AWS Secrets Manager or TFC/GitHub Secrets at runtime.
