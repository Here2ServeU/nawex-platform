# ------------------------------------------------------------------------------
# REGISTRY OUTPUTS
# ------------------------------------------------------------------------------

output "repository_url" {
  description = "The base URL for docker push/pull"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

# Principal Touch: The auth command
output "auth_command" {
  description = "Run this to configure local Docker client"
  value       = "gcloud auth configure-docker ${var.region}-docker.pkg.dev"
}
