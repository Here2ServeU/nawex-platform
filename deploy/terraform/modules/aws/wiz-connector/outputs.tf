output "role_arn" {
  description = "Paste into the Wiz AWS connector."
  value       = aws_iam_role.wiz.arn
}
