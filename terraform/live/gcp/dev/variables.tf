# ------------------------------------------------------------------------------
# EXPRESS WEB GCP VARIABLES
# ------------------------------------------------------------------------------
# Purpose: strict typing for GCP deployment parameters.
# ------------------------------------------------------------------------------

variable "project_id" {
  description = "The GCP Project ID hosting the environment."
  type        = string
  validation {
    condition     = length(var.project_id) > 0
    error_message = "Project ID must not be empty."
  }
}

variable "region" {
  description = "The GCP Region."
  type        = string
  default     = "us-central1" # Low carbon region
}

variable "labels" {
  description = "Global Governance Labels."
  type        = map(string)
  default = {
    project     = "express-web"
    environment = "dev"
    owner       = "platform-engineering"
    cost_center = "dev-101"
    managed_by  = "terraform"
  }
}

variable "gke_release_channel" {
  description = "Release channel for GKE upgrades."
  type        = string
  default     = "REGULAR"
}
