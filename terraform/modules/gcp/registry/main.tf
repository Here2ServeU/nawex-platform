# ------------------------------------------------------------------------------
# GCP ARTIFACT REGISTRY (SHARED)
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Provisions the central container image store.
# Strategy:    Uses Artifact Registry (Next-Gen) instead of Deprecated GCR.
# ------------------------------------------------------------------------------

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  # backend "gcs" { ... } 
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. The Artifact Repository
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = "express-web-images"
  description   = "Docker repository for Express Web workloads"
  format        = "DOCKER"

  labels = var.labels
}

# 2. IAM Policy (Allow GKE to pull)
# In a real scenario, you create a dedicated Service Account for GKE nodes
# and grant it "roles/artifactregistry.reader" on this repo.
