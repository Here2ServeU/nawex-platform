output "permission_set_arns" {
  description = "Permission set name -> ARN."
  value       = { for k, ps in aws_ssoadmin_permission_set.this : k => ps.arn }
}

output "assignment_count" {
  description = "Number of group x permission set x account assignments."
  value       = length(aws_ssoadmin_account_assignment.this)
}

output "groups" {
  description = "AD/SCIM group display name -> Identity Store group ID."
  value       = { for k, g in data.aws_identitystore_group.this : k => g.group_id }
}
