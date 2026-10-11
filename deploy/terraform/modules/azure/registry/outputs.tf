output "registry_name" {
  value = azurerm_container_registry.acr.name
}

output "registry_id" {
  description = "Needed for role assignments (AKS -> AcrPull)."
  value       = azurerm_container_registry.acr.id
}

output "login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "registry_url" {
  description = "Registry prefix for image.registry (append /<image>)."
  value       = "${azurerm_container_registry.acr.login_server}/${var.project}"
}

output "login_command" {
  value = "az acr login --name ${azurerm_container_registry.acr.name}"
}
