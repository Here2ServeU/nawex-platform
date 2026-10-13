output "arn" {
  description = "Boundary policy ARN; pass as permissions_boundary on every IAM role."
  value       = aws_iam_policy.boundary.arn
}

output "name" {
  description = "Boundary policy name (referenced by Identity Center permission sets)."
  value       = aws_iam_policy.boundary.name
}
