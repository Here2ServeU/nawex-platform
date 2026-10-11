# ------------------------------------------------------------------------------
# GCP ARTIFACT REGISTRY MODULE
# ------------------------------------------------------------------------------
# Docker repository holding golden-platform / golden-client-portal / golden-workload.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

resource "google_artifact_registry_repository" "repo" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repository_id
  description   = "Container images for the ${var.repository_id} platform"
  format        = "DOCKER"
  labels        = var.labels

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = var.keep_images
    }
  }
}
