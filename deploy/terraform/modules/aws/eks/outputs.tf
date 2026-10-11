output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  value = module.eks.cluster_certificate_authority_data
}

output "oidc_provider_arn" {
  value = module.eks.oidc_provider_arn
}

output "vpc_id" {
  value = module.vpc.vpc_id
}

output "private_subnets" {
  value = module.vpc.private_subnets
}

output "workload_role_arn" {
  description = "IAM role for the platform ServiceAccount (eks.amazonaws.com/role-arn)."
  value       = aws_iam_role.workload.arn
}

output "region" {
  value = var.region
}
