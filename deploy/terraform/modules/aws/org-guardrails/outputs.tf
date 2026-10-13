output "scp_ids" {
  description = "SCP name -> policy ID."
  value       = { for k, p in aws_organizations_policy.scp : k => p.id }
}

output "rcp_ids" {
  description = "RCP name -> policy ID."
  value       = { for k, p in aws_organizations_policy.rcp : k => p.id }
}

output "organization_id" {
  description = "Organization ID used for the data-perimeter conditions."
  value       = data.aws_organizations_organization.current.id
}
