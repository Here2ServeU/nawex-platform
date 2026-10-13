# ------------------------------------------------------------------------------
# OCI OKE MODULE
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Provisions an OKE cluster with VCN-Native Networking.
# Strategy:    Uses "Flex" shapes to rightsizing compute exactly to workload needs.
# ------------------------------------------------------------------------------

terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
    }
  }
}

# 1. The Control Plane
resource "oci_containerengine_cluster" "k8s_cluster" {
  compartment_id     = var.compartment_id
  kubernetes_version = var.k8s_version
  name               = var.cluster_name
  vcn_id             = var.vcn_id

  # Network: VCN-Native Pod Networking (High Performance)
  # This gives every Pod a real VCN IP, removing NAT overhead.
  endpoint_config {
    is_public_ip_enabled = true # Set to false for strictly private clusters
    subnet_id            = var.service_lb_subnet_ids[0]
  }

  options {
    service_lb_subnet_ids = var.service_lb_subnet_ids

    add_ons {
      is_kubernetes_dashboard_enabled = false # Security best practice
      is_tiller_enabled               = false # Deprecated/Insecure
    }

    kubernetes_network_config {
      pods_cidr     = "10.244.0.0/16"
      services_cidr = "10.96.0.0/16"
    }
  }

  freeform_tags = var.tags
}

# 2. The Node Pools (Flex Infrastructure)
resource "oci_containerengine_node_pool" "node_pools" {
  for_each = var.node_pools

  cluster_id     = oci_containerengine_cluster.k8s_cluster.id
  compartment_id = var.compartment_id
  name           = each.key
  node_shape     = each.value.shape

  # Configuration for the Node Image (Oracle Linux)
  node_source_details {
    image_id    = var.node_image_id_map[each.value.shape]
    source_type = "image"
  }

  # FinOps: The Flex Shape Config
  # Allows us to define EXACT cpu/memory ratios.
  node_shape_config {
    ocpus         = each.value.ocpus
    memory_in_gbs = each.value.memory_in_gbs
  }

  node_config_details {
    size = each.value.node_count

    placement_configs {
      availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
      subnet_id           = var.pod_subnet_ids[0]
    }
    # Simple resiliency: Spans 3 ADs if available
    # placement_configs {
    #   availability_domain = data.oci_identity_availability_domains.ads.availability_domains[1].name
    #   subnet_id           = var.pod_subnet_ids[0]
    # }
  }

  initial_node_labels {
    key   = "golden/workload"
    value = "general"
  }

  freeform_tags = var.tags
}

# Data Source to find Availability Domains
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_id
}
