output "management_group_ids" {
  description = "Management group key (access-model scope) -> resource ID."
  value       = local.mg_ids
}

output "policy_assignment_ids" {
  description = "Policy assignment name -> ID."
  value = merge(
    { for k, a in azurerm_management_group_policy_assignment.this : k => a.id },
    { for a in azurerm_management_group_policy_assignment.defender : a.name => a.id },
  )
}

output "groups" {
  description = "Entra group display name -> object ID (synced from AD)."
  value       = { for k, g in data.azuread_group.persona : k => g.object_id }
}

output "active_assignment_count" {
  description = "Standing group x role x scope assignments."
  value       = length(azurerm_role_assignment.persona)
}

output "eligible_assignment_count" {
  description = "PIM-eligible group x role x scope assignments."
  value       = length(azurerm_pim_eligible_role_assignment.persona)
}
