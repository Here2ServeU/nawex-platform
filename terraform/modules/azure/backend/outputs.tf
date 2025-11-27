# ------------------------------------------------------------------------------
# BOOTSTRAP OUTPUTS
# ------------------------------------------------------------------------------

output "resource_group_name" {
  value = azurerm_resource_group.tfstate.name
}

output "storage_account_name" {
  description = "The globally unique name of the storage account"
  value       = azurerm_storage_account.tfstate.name
}

output "container_name_dev" {
  value = azurerm_storage_container.dev_state.name
}

# Principal Touch: Generate the code block for the user
output "backend_config_instruction" {
  description = "Copy this block into your terraform/live/azure/dev/main.tf"
  value       = <<EOT
  backend "azurerm" {
    resource_group_name  = "${azurerm_resource_group.tfstate.name}"
    storage_account_name = "${azurerm_storage_account.tfstate.name}"
    container_name       = "${azurerm_storage_container.dev_state.name}"
    key                  = "express-web.dev.terraform.tfstate"
  }
  EOT
}
