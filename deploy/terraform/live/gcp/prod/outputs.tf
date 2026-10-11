# Uniform outputs consumed by scripts/deploy.sh.
output "cluster_name" {
  value = module.gke.cluster_name
}

output "cluster_endpoint" {
  value     = module.gke.endpoint
  sensitive = true
}

output "registry_url" {
  description = "Value for the chart's image.registry."
  value       = module.registry.registry_url
}

output "kubeconfig_command" {
  value = "gcloud container clusters get-credentials ${module.gke.cluster_name} --location ${module.gke.location} --project ${var.project_id}"
}

output "workload_identity" {
  description = "Google service account for the golden ServiceAccount (iam.gke.io/gcp-service-account)."
  value       = module.gke.workload_gsa_email
}
