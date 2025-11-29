# ------------------------------------------------------------------------------
# WEB-APP GCP DEV - MAIN ENTRY POINT
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Instantiates the GCP footprint (GKE + VPC) for the web-app.
# Strategy:    Zonal GKE for Cost Efficiency (Dev). VPC-Native for Performance.
# ------------------------------------------------------------------------------
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project        = var.project_id
  region         = var.region
  # Principal Note: Standardizing labels at the provider level for full coverage
  default_labels = var.labels
}

# 1. Network Layer (The VPC)
# Utilizing the Google Cloud Foundation Fabric or Standard Module
module "vpc" {
  source  = "terraform-google-modules/network/google"
  version = "~> 9.0"
  project_id   = var.project_id
  network_name = "web-app-dev-vpc"
  routing_mode = "GLOBAL"
  subnets = [
    {
      subnet_name   = "gke-subnet"
      subnet_ip     = "10.10.0.0/24"
      subnet_region = var.region
    }
  ]
  # Secondary ranges are REQUIRED for VPC-Native GKE (Pod & Service IPs)
  secondary_ranges = {
    "gke-subnet" = [
      {
        range_name    = "gke-pods"
        ip_cidr_range = "10.20.0.0/16"
      },
      {
        range_name    = "gke-services"
        ip_cidr_range = "10.30.0.0/20"
      }
    ]
  }
}

# 2. Compute Layer (GKE Cluster)
# Consuming our proprietary internal module
module "gke_cluster" {
  source       = "../../../modules/compute/gcp-gke"
  cluster_name = "web-app-dev-gke-01"
  project_id   = var.project_id
  region       = var.region
  # Principal FinOps: Use Zonal for Dev to save ~$70/mo on control plane fees
  # and reduce cross-zone traffic costs.
  zones        = ["us-central1-a"]
  network      = module.vpc.network_name
  subnetwork   = module.vpc.subnets_names[0]
  
  # Networking
  ip_range_pods     = "gke-pods"
  ip_range_services = "gke-services"

  # Identity
  enable_workload_identity = true # The modern standard replacing Service Account keys
  
  # Node Pools
  # We use Preemptible VMs (Google's Spot equivalent) for the Dev workload
  node_pools = [
    {
      name         = "web-app-dev-pool"
      machine_type = "e2-medium"
      min_count    = 1
      max_count    = 3
      preemptible  = true # massive cost savings for Dev
      auto_repair  = true
      auto_upgrade = true
    }
  ]
}
