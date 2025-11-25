terraform {
  required_version = ">= 1.3.0"
  backend "gcs" {
    bucket = "emmanuel-tf-state-11202025"
    prefix = "gcp/dev"
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

module "registry" {
  source   = "../../modules/gcp/registry"
  project  = var.project
  region   = var.region
  repo_name = "t2s-express-repo"
}

module "gke" {
  source   = "../../modules/gcp/gke"
  project  = var.project
  region   = var.region
  name     = "t2s-gke-dev"
  location = var.region
  network    = "default"
  subnetwork = "default"
}
