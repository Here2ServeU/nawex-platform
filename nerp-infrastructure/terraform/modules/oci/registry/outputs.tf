# ------------------------------------------------------------------------------
# REGISTRY OUTPUTS
# ------------------------------------------------------------------------------

output "repo_url" {
  description = "The OCIR URL"
  value       = "${var.region}.ocir.io/${var.tenancy_namespace}/express-web/app"
}

output "repo_id" {
  value = oci_artifacts_container_repository.repo.id
}

# Principal Touch: OCI Login is region specific
output "docker_login_command" {
  description = "Command to auth Docker against OCIR"
  value       = "docker login ${var.region}.ocir.io"
}
