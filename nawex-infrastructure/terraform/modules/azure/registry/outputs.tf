# ------------------------------------------------------------------------------
# REGISTRY OUTPUTS
# ------------------------------------------------------------------------------

output "registry_name" {
  value = azurerm_container_registry.acr.name
}

output "login_server" {
  description = "The URL to use in Docker push commands"
  value       = azurerm_container_registry.acr.login_server
}

output "registry_id" {
  description = "Needed for Role Assignments (AKS -> AcrPull)"
  value       = azurerm_container_registry.acr.id
}

# Principal Touch: The setup command for local pushing
output "login_command" {
  description = "Command for developers to push images manually"
  value       = "az acr login --name ${azurerm_container_registry.acr.name}"
}
