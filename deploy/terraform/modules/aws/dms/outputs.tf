output "replication_instance_arn" {
  description = "Provisioned replication instance ARN (null when serverless)."
  value       = var.serverless ? null : aws_dms_replication_instance.this[0].replication_instance_arn
}

output "replication_task_arn" {
  description = "Replication task ARN (null when serverless). Start it with `aws dms start-replication-task`."
  value       = var.serverless ? null : aws_dms_replication_task.this[0].replication_task_arn
}

output "replication_config_arn" {
  description = "Serverless replication config ARN (null when provisioned)."
  value       = var.serverless ? aws_dms_replication_config.this[0].arn : null
}

output "source_endpoint_arn" {
  value = aws_dms_endpoint.source.endpoint_arn
}

output "target_endpoint_arn" {
  value = aws_dms_endpoint.target.endpoint_arn
}

output "kms_key_arn" {
  value = local.kms_key_arn
}

output "secrets_access_role_arn" {
  value = aws_iam_role.secrets.arn
}

output "cdc_latency_alarm_arns" {
  value = { for k, a in aws_cloudwatch_metric_alarm.cdc_latency : k => a.arn }
}
