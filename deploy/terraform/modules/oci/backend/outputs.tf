# ------------------------------------------------------------------------------
# BOOTSTRAP OUTPUTS
# ------------------------------------------------------------------------------

output "bucket_name" {
  value = oci_objectstorage_bucket.tfstate.name
}

output "namespace" {
  value = data.oci_objectstorage_namespace.ns.namespace
}

# Principal Touch: OCI backend config is tricky (S3 compatible vs HTTP). 
# We provide the Standard HTTP backend block.
output "backend_config_instruction" {
  value = <<EOT
  # ----------------------------------------------------------------
  # OCI BACKEND CONFIGURATION
  # ----------------------------------------------------------------
  backend "http" {
    address       = "https://objectstorage.${var.region}.oraclecloud.com/p/{preauth_request_id}/n/${data.oci_objectstorage_namespace.ns.namespace}/b/${oci_objectstorage_bucket.tfstate.name}/o/terraform.tfstate"
    update_method = "PUT"
  }
  # Note: For production, we recommend using the OCI S3 Compatibility API
  # endpoint for state locking support.
  EOT
}
