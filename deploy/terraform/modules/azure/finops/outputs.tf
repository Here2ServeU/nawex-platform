output "budget_ids" {
  description = "Budget name -> ID for the subscription, team and resource group budgets."
  value = merge(
    { (azurerm_consumption_budget_subscription.monthly.name) = azurerm_consumption_budget_subscription.monthly.id },
    { for b in azurerm_consumption_budget_subscription.team : b.name => b.id },
    { for b in azurerm_consumption_budget_resource_group.this : b.name => b.id },
  )
}

output "export_storage_account_id" {
  description = "Storage account receiving cost exports (null when the export is disabled)."
  value       = local.export_enabled ? azurerm_storage_account.exports[0].id : null
}

output "export_container_id" {
  description = "Resource manager ID of the export container (null when the export is disabled)."
  value       = local.export_enabled ? azurerm_storage_container.exports[0].resource_manager_id : null
}

output "required_tags" {
  description = "Required tag keys, for wiring Azure Policy 'Require a tag on resources' assignments."
  value       = var.required_tags
}
