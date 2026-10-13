output "organization_id" {
  value = module.org_guardrails.organization_id
}

output "scp_ids" {
  value = module.org_guardrails.scp_ids
}

output "rcp_ids" {
  value = module.org_guardrails.rcp_ids
}

output "permission_set_arns" {
  value = try(module.identity_center[0].permission_set_arns, {})
}

output "assignment_count" {
  value = try(module.identity_center[0].assignment_count, 0)
}
