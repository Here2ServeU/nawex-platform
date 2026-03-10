# ------------------------------------------------------------------------------
# OCI TERRAFORM BOOTSTRAP
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Provisions Object Storage for Terraform State.
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

# Get the Object Storage Namespace (Specific to Tenancy)
data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.compartment_id
}

# 1. The State Bucket
resource "oci_objectstorage_bucket" "tfstate" {
  compartment_id = var.compartment_id
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = "express-web-tfstate"
  access_type    = "NoPublicAccess"
  
  versioning = "Enabled" # Critical for rollback

  freeform_tags = var.tags
}
