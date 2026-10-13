output "cluster_id" {
  value = azurerm_kubernetes_cluster.this.id
}

output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "host" {
  description = "Kubernetes API server endpoint."
  value       = azurerm_kubernetes_cluster.this.kube_config[0].host
  sensitive   = true
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL (GitHub Actions / Workload Identity federation)."
  value       = azurerm_kubernetes_cluster.this.oidc_issuer_url
}

output "kubelet_identity_object_id" {
  description = "Object ID of the kubelet identity (grant AcrPull to this)."
  value       = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}

output "workload_client_id" {
  description = "Client ID of the workload managed identity (azure.workload.identity/client-id)."
  value       = azurerm_user_assigned_identity.workload.client_id
}
