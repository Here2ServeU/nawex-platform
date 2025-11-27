# ------------------------------------------------------------------------------
# Purpose: Exposes critical connection endpoints and operational commands.
# ------------------------------------------------------------------------------

output "vpc_id" {
  description = "The ID of the Production VPC"
  value       = module.vpc.vpc_id
}

output "cluster_endpoint" {
  description = "The EKS Control Plane Endpoint (HTTPS)"
  value       = module.eks_cluster.cluster_endpoint
}

output "cluster_name" {
  description = "The name of the Kubernetes Cluster"
  value       = "nexus-prod-01"
}

# --- The "Principal" Touch ---
# Don't make the user guess how to connect. Give them the command.
output "connect_command" {
  description = "Run this command to configure kubectl for this cluster"
  value       = "aws eks update-kubeconfig --region us-east-1 --name nexus-prod-01"
}

output "region" {
  description = "AWS Region"
  value       = var.region
}
