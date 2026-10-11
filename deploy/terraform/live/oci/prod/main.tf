# ------------------------------------------------------------------------------
# GOLDEN OCI - MAIN ENTRY POINT
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Instantiates the OKE (Kubernetes) footprint on Oracle Cloud.
# Strategy:    Utilizes "Flex" shapes for precision rightsizing (FinOps).
# ------------------------------------------------------------------------------
terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.0"
    }
  }
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

# 1. Governance Layer (Compartment)
# We assume the compartment is already created by the Landing Zone,
# but we reference it here to enforce boundary.
data "oci_identity_compartment" "dev" {
  id = var.compartment_id
}

# 2. Network Layer (VCN)
# Using the VCN native pod networking for maximum performance
module "vcn" {
  source         = "oracle-terraform-modules/vcn/oci"
  version        = "3.6.0"
  compartment_id = var.compartment_id
  region         = var.region
  vcn_name       = "${var.project}-prod-vcn"
  vcn_dns_label  = "goldenprod"
  # Principal Choice: CIDR planning to avoid overlap with on-prem
  vcn_cidrs               = ["10.0.0.0/16"]
  create_internet_gateway = true
  create_nat_gateway      = true
  create_service_gateway  = true # Access Object Storage without internet

  # Private subnet shared by OKE worker nodes, pods and internal load balancers.
  subnets = {
    oke = {
      name       = "oke"
      cidr_block = "10.0.1.0/24"
      type       = "private"
      dns_label  = "oke"
    }
  }
}

# 3. Compute Layer (OKE Cluster)
module "oke_cluster" {
  source         = "../../../modules/oci/oke"
  cluster_name   = "${var.project}-prod-oke-01"
  compartment_id = var.compartment_id
  vcn_id         = module.vcn.vcn_id
  # Kubernetes Version
  k8s_version = "v1.29.1"
  # Networking
  # Using OCI VCN-Native Pod Networking (CNI)
  pod_subnet_ids        = values(module.vcn.subnet_id)
  service_lb_subnet_ids = values(module.vcn.subnet_id)
  # Node Pools (The "Flex" Strategy)
  node_pools = {
    app_pool = {
      shape            = "VM.Standard.E4.Flex" # AMD EPYC (High Perf/Cost Ratio)
      ocpus            = 1                     # Exact sizing
      memory_in_gbs    = 8                     # Exact sizing
      node_count       = 2
      boot_volume_size = 50
    }
  }
  tags = var.defined_tags
}
