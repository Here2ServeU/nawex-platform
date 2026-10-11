# Uniform outputs consumed by scripts/deploy.sh.
output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "registry_url" {
  description = "Value for the chart's image.registry."
  value       = module.registry.registry_url
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${module.eks.cluster_name}"
}

output "workload_identity" {
  description = "IAM role ARN for the golden ServiceAccount (eks.amazonaws.com/role-arn)."
  value       = module.eks.workload_role_arn
}
