# ------------------------------------------------------------------------------
# GCP GKE MODULE
# ------------------------------------------------------------------------------
# VPC-native private GKE cluster with Workload Identity, a general node pool,
# an optional NVIDIA GPU node pool and a Google service account bound to the
# platform Kubernetes ServiceAccount.
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

locals {
  location = var.regional ? var.region : "${var.region}-${var.zone_suffix}"
}

# ---------------------------------------------------------------- network ----
resource "google_compute_network" "this" {
  project                 = var.project_id
  name                    = "${var.name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "nodes" {
  project                  = var.project_id
  name                     = "${var.name}-nodes"
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = var.nodes_cidr
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.services_cidr
  }
}

resource "google_compute_router" "this" {
  project = var.project_id
  name    = "${var.name}-router"
  region  = var.region
  network = google_compute_network.this.id
}

resource "google_compute_router_nat" "this" {
  project                            = var.project_id
  name                               = "${var.name}-nat"
  router                             = google_compute_router.this.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# ------------------------------------------------------- node identity -------
resource "google_service_account" "nodes" {
  project      = var.project_id
  account_id   = substr("${var.name}-nodes", 0, 30)
  display_name = "GKE nodes for ${var.name}"
}

resource "google_project_iam_member" "nodes" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer",
    "roles/artifactregistry.reader",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.nodes.email}"
}

# ---------------------------------------------------------------- cluster ----
resource "google_container_cluster" "primary" {
  project  = var.project_id
  name     = var.name
  location = local.location

  min_master_version = var.kubernetes_version
  networking_mode    = "VPC_NATIVE"
  network            = google_compute_network.this.id
  subnetwork         = google_compute_subnetwork.nodes.id

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # API server exposure: allow-listed public endpoint, or private endpoint only.
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = length(var.api_server_authorized_cidrs) == 0
    master_ipv4_cidr_block  = var.master_cidr
  }

  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.api_server_authorized_cidrs
      content {
        cidr_block   = cidr_blocks.value
        display_name = "authorized-${cidr_blocks.key}"
      }
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = var.release_channel
  }

  # Node pools are managed separately.
  remove_default_node_pool = true
  initial_node_count       = 1

  deletion_protection = var.deletion_protection
  resource_labels     = var.labels
}

resource "google_container_node_pool" "general" {
  project  = var.project_id
  name     = "general"
  location = local.location
  cluster  = google_container_cluster.primary.name

  initial_node_count = var.node_count

  autoscaling {
    min_node_count = var.node_min_count
    max_node_count = var.node_max_count
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = var.node_instance_type
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = merge(var.labels, { "workload-type" = "general" })

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    metadata = {
      disable-legacy-endpoints = "true"
    }

    shielded_instance_config {
      enable_secure_boot = true
    }
  }

  lifecycle {
    ignore_changes = [initial_node_count]
  }
}

resource "google_container_node_pool" "gpu" {
  count    = var.gpu_node_pool_enabled ? 1 : 0
  project  = var.project_id
  name     = "gpu"
  location = local.location
  cluster  = google_container_cluster.primary.name

  initial_node_count = var.gpu_node_count

  autoscaling {
    min_node_count = 0
    max_node_count = max(var.gpu_node_count, 1)
  }

  node_config {
    machine_type    = var.gpu_instance_type
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = merge(var.labels, { "nvidia.com/gpu.present" = "true" })

    guest_accelerator {
      type  = var.gpu_accelerator_type
      count = 1
      gpu_driver_installation_config {
        gpu_driver_version = "DEFAULT"
      }
    }

    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }

  lifecycle {
    ignore_changes = [initial_node_count]
  }
}

# ------------------------------------------------- workload identity ---------
resource "google_service_account" "workload" {
  project      = var.project_id
  account_id   = substr("${var.name}-workload", 0, 30)
  display_name = "Platform workload identity for ${var.name}"
}

resource "google_service_account_iam_member" "workload" {
  service_account_id = google_service_account.workload.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.workload_namespace}/${var.workload_service_account}]"

  depends_on = [google_container_cluster.primary]
}
