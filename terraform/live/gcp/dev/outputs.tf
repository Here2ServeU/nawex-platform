# ------------------------------------------------------------------------------
# EXPRESS WEB GCP OUTPUTS
# ------------------------------------------------------------------------------
# Purpose: Operational hand-off data.
# ------------------------------------------------------------------------------

output "network_name" {
  description = "The VPC Name"
  value       = module.vpc.network_name
}

output "cluster_name" {
  description = "The GKE Cluster Name"
  value       = "express-web-dev-gke-01"
}

output "cluster_endpoint" {
  description = "The Public Endpoint for the API Server"
  value       = module.gke_cluster.endpoint
  sensitive   = true
}

# --- The "Principal" Touch ---
output "connect_command" {
  description = "Copy/Paste this to access the cluster via GCloud SDK"
  value       = "gcloud container clusters get-credentials express-web-dev-gke-01 --region us-central1-a --project ${var.project_id}"
}

output "cluster_location" {
  description = "The Zone or Region of the cluster"
  value       = module.gke_cluster.location
}
