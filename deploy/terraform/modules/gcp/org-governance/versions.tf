terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source = "hashicorp/google"
      # google_privileged_access_manager_entitlement is GA from 5.x (validated on 5.45).
      version = ">= 5.40, < 6.0"
    }
  }
}
