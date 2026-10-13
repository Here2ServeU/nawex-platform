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

output "karpenter_controller_role_arn" {
  description = "IRSA role of the Karpenter controller (null when karpenter_enabled = false)."
  value       = try(module.karpenter[0].iam_role_arn, null)
}

output "karpenter_node_role_name" {
  description = "IAM role for Karpenter nodes; set EC2NodeClass spec.role to this."
  value       = try(module.karpenter[0].node_iam_role_name, null)
}

output "karpenter_interruption_queue_name" {
  description = "SQS queue receiving spot interruption / rebalance / health events."
  value       = try(module.karpenter[0].queue_name, null)
}

output "velero_bucket_name" {
  description = "S3 bucket holding Velero backups (null when velero_enabled = false)."
  value       = try(aws_s3_bucket.velero[0].id, null)
}

output "velero_role_arn" {
  description = "IRSA role of the Velero server."
  value       = try(aws_iam_role.velero[0].arn, null)
}

output "velero_kms_key_arn" {
  description = "KMS key encrypting the Velero bucket."
  value       = try(aws_kms_key.velero[0].arn, null)
}
