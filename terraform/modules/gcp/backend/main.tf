output "endpoint" {
  value     = google_container_cluster.primary.endpoint
  sensitive = true
}

output "location" {
  value = google_container_cluster.primary.location
}

output "name" {
  value = google_container_cluster.primary.name
}

# Principal Touch: Needed to configure IAM bindings for Workload Identity
output "workload_identity_pool" {
  description = "The Workload Identity Pool ID"
  value       = google_container_cluster.primary.workload_identity_config[0].workload_pool
}
