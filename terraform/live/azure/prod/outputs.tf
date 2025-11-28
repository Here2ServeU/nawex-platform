# ------------------------------------------------------------------------------
# Purpose: Operational hand-off data.
# ------------------------------------------------------------------------------

output "resource_group_name" {
  description = "The logical container for billing aggregation"
  value       = azurerm_resource_group.main.name
}

output "aks_cluster_name" {
  value = "express-web-aks-01"
}

output "aks_host" {
  description = "Private Endpoint for the API Server"
  value       = module.aks_cluster.host
  sensitive   = true # Mask in CI logs for security
}

# --- The "Principal" Touch ---
output "connect_command" {
  description = "Copy/Paste this to access the cluster"
  value       = "az aks get-credentials --resource-group nexus-prod-rg --name nexus-prod-aks-01 --overwrite-existing"
}

output "oidc_issuer_url" {
  description = "Used for Workload Identity Federation (Keyless Auth)"
  value       = module.aks_cluster.oidc_issuer_url
}
