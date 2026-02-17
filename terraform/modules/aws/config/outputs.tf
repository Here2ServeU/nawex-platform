output "config_bucket_name" {
  description = "S3 bucket used for AWS Config delivery."
  value       = var.create_bucket ? aws_s3_bucket.config[0].bucket : var.bucket_name
}

output "config_recorder_name" {
  description = "AWS Config recorder name."
  value       = aws_config_configuration_recorder.this.name
}

output "config_role_arn" {
  description = "IAM role ARN for the Config recorder."
  value       = aws_iam_role.config.arn
}
