output "cluster_name" {
  value = google_container_cluster.primary.name
}

output "location" {
  value = google_container_cluster.primary.location
}

output "endpoint" {
  value     = google_container_cluster.primary.endpoint
  sensitive = true
}

output "workload_identity_pool" {
  value = google_container_cluster.primary.workload_identity_config[0].workload_pool
}

output "workload_gsa_email" {
  description = "GSA for the platform ServiceAccount (iam.gke.io/gcp-service-account)."
  value       = google_service_account.workload.email
}

output "network" {
  value = google_compute_network.this.name
}
