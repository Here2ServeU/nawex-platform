# ------------------------------------------------------------------------------
# EXPRESS WEB AZURE DEV OUTPUTS
# ------------------------------------------------------------------------------

output "aks_resource_group" {
  value = azurerm_resource_group.dev.name
}

output "aks_cluster_name" {
  value = "express-web-dev-aks-01"
}

# Principal Touch: The exact command needed to start working
output "connect_command" {
  description = "Developer Onboarding Command"
  value       = "az aks get-credentials --resource-group express-web-dev-rg --name express-web-dev-aks-01 --overwrite-existing"
}

output "oidc_issuer_url" {
  description = "Required for setting up GitHub Actions OIDC"
  value       = module.aks_cluster.oidc_issuer_url
}
