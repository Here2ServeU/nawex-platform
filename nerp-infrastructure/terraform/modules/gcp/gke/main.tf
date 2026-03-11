# ------------------------------------------------------------------------------
# EXPRESS WEB GKE MODULE
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Provisions a VPC-Native GKE Cluster with Workload Identity.
# Strategy:    Decouples the Control Plane from the Node Pools for lifecycle safety.
# ------------------------------------------------------------------------------

# 1. The Control Plane
resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = length(var.zones) > 1 ? var.region : var.zones[0] # Regional vs Zonal logic
  
  # Network: VPC-Native is mandatory for high performance and Pod IP visibility
  networking_mode = "VPC_NATIVE"
  network         = var.network
  subnetwork      = var.subnetwork

  ip_allocation_policy {
    cluster_secondary_range_name  = var.ip_range_pods
    services_secondary_range_name = var.ip_range_services
  }

  # Security: Enable Workload Identity (GSA <-> KSA mapping)
  # This replaces vulnerable static JSON keys.
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # FinOps: Remove default node pool immediately to use custom managed pools
  remove_default_node_pool = true
  initial_node_count       = 1
  
  # Lifecycle: Prevent accidental deletion of the control plane
  deletion_protection = false # Set to true for Prod
}

# 2. The Node Pools
# We use a dynamic block to create multiple pools (e.g., System vs. Workload)
resource "google_container_node_pool" "pools" {
  for_each = { for pool in var.node_pools : pool.name => pool }

  name       = each.value.name
  location   = length(var.zones) > 1 ? var.region : var.zones[0]
  cluster    = google_container_cluster.primary.name
  node_count = lookup(each.value, "min_count", 1)

  autoscaling {
    min_node_count = lookup(each.value, "min_count", 1)
    max_node_count = lookup(each.value, "max_node_count", 3)
  }

  node_config {
    machine_type = lookup(each.value, "machine_type", "e2-medium")
    
    # FinOps: Spot VM support (GCP calls them "SPOT" or "PREEMPTIBLE")
    spot = lookup(each.value, "preemptible", false)

    # Security: Use a dedicated Service Account, not the default Compute Engine SA
    service_account = var.node_service_account # Least Privilege
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    # Metadata required for Workload Identity
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
    
    labels = var.labels
  }
  
  lifecycle {
    ignore_changes = [initial_node_count]
  }
}
