# Uniform outputs consumed by scripts/deploy.sh.
output "cluster_name" {
  value = module.aks.cluster_name
}

output "cluster_endpoint" {
  value     = module.aks.host
  sensitive = true
}

output "registry_url" {
  description = "Value for the chart's image.registry."
  value       = module.registry.registry_url
}

output "kubeconfig_command" {
  value = "az aks get-credentials --resource-group ${azurerm_resource_group.this.name} --name ${module.aks.cluster_name} --overwrite-existing"
}

output "workload_identity" {
  description = "Managed identity client ID for the golden ServiceAccount (azure.workload.identity/client-id)."
  value       = module.aks.workload_client_id
}
