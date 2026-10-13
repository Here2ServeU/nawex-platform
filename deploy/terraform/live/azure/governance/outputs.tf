output "management_group_ids" {
  value = module.governance.management_group_ids
}

output "policy_assignment_ids" {
  value = module.governance.policy_assignment_ids
}

output "active_assignment_count" {
  value = module.governance.active_assignment_count
}

output "eligible_assignment_count" {
  value = module.governance.eligible_assignment_count
}
