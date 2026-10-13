# ------------------------------------------------------------------------------
# GCP REMOTE STATE BOOTSTRAP
# ------------------------------------------------------------------------------
# Creates the versioned, uniform-access GCS bucket that stores Terraform state
# for the GCP environments. Run once per project with local state.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "tfstate" {
  name                        = "${var.name_prefix}-tfstate-${random_id.suffix.hex}"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = var.labels

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 10
    }
    action {
      type = "Delete"
    }
  }
}
