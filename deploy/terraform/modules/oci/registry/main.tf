# ------------------------------------------------------------------------------
# OCI CONTAINER REGISTRY (SHARED)
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Provisions the centralized OCIR for Golden platform images.
# ------------------------------------------------------------------------------

terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
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

# Tenancy Object Storage namespace (part of every OCIR URL).
data "oci_objectstorage_namespace" "this" {
  compartment_id = var.tenancy_ocid
}

# 1. Container Repository
resource "oci_artifacts_container_repository" "repo" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}/golden-platform"
  is_public      = false # Zero Trust default
  is_immutable   = false # Allow overwriting tags in Dev (True for Prod)

  freeform_tags = var.tags
}
