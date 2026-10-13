output "cluster_id" {
  description = "Aurora cluster identifier."
  value       = aws_rds_cluster.this.id
}

output "cluster_arn" {
  description = "Aurora cluster ARN."
  value       = aws_rds_cluster.this.arn
}

output "cluster_resource_id" {
  description = "Cluster resource id (used in rds-db:connect IAM policies)."
  value       = aws_rds_cluster.this.cluster_resource_id
}

output "writer_endpoint" {
  description = "Cluster (writer) endpoint."
  value       = aws_rds_cluster.this.endpoint
}

output "reader_endpoint" {
  description = "Load-balanced reader endpoint."
  value       = aws_rds_cluster.this.reader_endpoint
}

output "proxy_endpoint" {
  description = "RDS Proxy read/write endpoint (null when the proxy is disabled)."
  value       = var.enable_proxy ? aws_db_proxy.this[0].endpoint : null
}

output "proxy_read_only_endpoint" {
  description = "RDS Proxy read-only endpoint (null without readers or proxy)."
  value       = length(aws_db_proxy_endpoint.read_only) > 0 ? aws_db_proxy_endpoint.read_only[0].endpoint : null
}

output "master_user_secret_arn" {
  description = "Secrets Manager secret holding the managed master credentials."
  value       = aws_rds_cluster.this.master_user_secret[0].secret_arn
}

output "iam_auth_resource_prefix" {
  description = "Append '/<db_user>' to build the rds-db:connect resource for IAM database authentication."
  value       = "arn:${local.partition}:rds-db:${local.region}:${local.account_id}:dbuser:${aws_rds_cluster.this.cluster_resource_id}"
}

output "kms_key_arn" {
  description = "KMS key used for storage, Performance Insights and the master secret."
  value       = local.kms_key_arn
}

output "cluster_parameter_group" {
  description = "Cluster parameter group name."
  value       = aws_rds_cluster_parameter_group.this.name
}

output "instance_parameter_group" {
  description = "Instance parameter group name."
  value       = aws_db_parameter_group.this.name
}

output "instance_ids" {
  description = "Terraform-managed instance identifiers (writer first)."
  value       = local.instance_ids
}
