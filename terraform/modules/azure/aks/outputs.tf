# ------------------------------------------------------------------------------
# EXPRESS WEB AWS DEV OUTPUTS
# ------------------------------------------------------------------------------

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

# Principal Touch: One-liner for dev access
output "connect_command" {
  description = "Run this to configure kubectl"
  value       = "aws eks update-kubeconfig --region us-east-1 --name express-web-dev-eks-01"
}
