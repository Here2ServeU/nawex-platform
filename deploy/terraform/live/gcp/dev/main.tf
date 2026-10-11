# ------------------------------------------------------------------------------
# Golden platform landing zone - GCP / dev
# Generated layout: every live/{aws,azure,gcp}/{dev,staging,prod} directory
# exposes the same inputs (variables.tf) and outputs (outputs.tf).
# ------------------------------------------------------------------------------

locals {
  name = "${var.project}-${var.environment}"
  labels = merge({
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
  }, { for k, v in var.tags : lower(k) => lower(v) })
}

resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "registry" {
  source        = "../../../modules/gcp/registry"
  project_id    = var.project_id
  region        = var.region
  repository_id = "${var.project}-${var.environment}"
  labels        = local.labels

  depends_on = [google_project_service.apis]
}

module "gke" {
  source = "../../../modules/gcp/gke"

  project_id          = var.project_id
  region              = var.region
  name                = local.name
  regional            = var.environment == "prod"
  kubernetes_version  = var.kubernetes_version
  deletion_protection = var.environment == "prod"

  node_count         = var.node_count
  node_instance_type = var.node_instance_type

  gpu_node_pool_enabled = var.gpu_node_pool_enabled
  gpu_instance_type     = var.gpu_instance_type
  gpu_node_count        = var.gpu_node_count

  labels = local.labels

  depends_on = [google_project_service.apis]
}
