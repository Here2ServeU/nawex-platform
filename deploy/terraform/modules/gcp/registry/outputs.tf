output "registry_url" {
  description = "Registry prefix for image.registry (append /<image>)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "repository_url" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}

output "auth_command" {
  value = "gcloud auth configure-docker ${var.region}-docker.pkg.dev"
}
