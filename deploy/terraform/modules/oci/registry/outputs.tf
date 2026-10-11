# ------------------------------------------------------------------------------
# REGISTRY OUTPUTS
# ------------------------------------------------------------------------------

output "repo_url" {
  description = "The OCIR URL"
  value       = "${var.region}.ocir.io/${data.oci_objectstorage_namespace.this.namespace}/${oci_artifacts_container_repository.repo.display_name}"
}

output "repo_id" {
  value = oci_artifacts_container_repository.repo.id
}

# Principal Touch: OCI Login is region specific
output "docker_login_command" {
  description = "Command to auth Docker against OCIR"
  value       = "docker login ${var.region}.ocir.io"
}
