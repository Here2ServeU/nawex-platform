terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

# Cloud Identity lookups and org-level APIs bill a quota project; run as the org
# admin / Terraform deployer service account (impersonation recommended).
provider "google" {
  billing_project       = var.quota_project
  user_project_override = true
}
