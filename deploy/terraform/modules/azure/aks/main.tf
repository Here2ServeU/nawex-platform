# ------------------------------------------------------------------------------
# AZURE AKS MODULE
# ------------------------------------------------------------------------------
# Description: Provisions an AKS cluster with a system node pool, an optional
#              Spot user node pool and an optional GPU node pool. OIDC issuer
#              and Workload Identity are enabled for keyless CI/CD access.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = var.location
  resource_group_name = var.resource_group_name
  dns_prefix          = var.cluster_name
  kubernetes_version  = var.kubernetes_version
  sku_tier            = var.sku_tier

  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  default_node_pool {
    name                = "system"
    vm_size             = var.node_instance_type
    vnet_subnet_id      = var.vnet_subnet_id
    enable_auto_scaling = true
    node_count          = var.node_count
    min_count           = var.node_min_count
    max_count           = var.node_max_count
    tags                = var.tags
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin = "azure"
    network_policy = "azure"
  }

  tags = var.tags
}

# FinOps: Spot capacity for interruptible application workloads.
resource "azurerm_kubernetes_cluster_node_pool" "spot" {
  count                 = var.enable_spot_instances ? 1 : 0
  name                  = "spot"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.node_instance_type
  vnet_subnet_id        = var.vnet_subnet_id
  priority              = "Spot"
  eviction_policy       = "Delete"
  spot_max_price        = -1
  enable_auto_scaling   = true
  min_count             = 0
  max_count             = var.user_max_count
  node_labels = {
    "kubernetes.azure.com/scalesetpriority" = "spot"
  }
  node_taints = ["kubernetes.azure.com/scalesetpriority=spot:NoSchedule"]
  tags        = var.tags
}

# GPU / AI-infrastructure workloads (gpu-optimizer). Disabled by default.
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  count                 = var.gpu_node_pool_enabled ? 1 : 0
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.gpu_instance_type
  vnet_subnet_id        = var.vnet_subnet_id
  enable_auto_scaling   = true
  node_count            = var.gpu_node_count
  min_count             = 0
  max_count             = max(var.gpu_node_count, 1)
  node_labels = {
    "nvidia.com/gpu.present" = "true"
  }
  node_taints = ["nvidia.com/gpu=present:NoSchedule"]
  tags        = var.tags
}

# ------------------------------------------------------------------------------
# Workload identity for the platform ServiceAccount
# (annotate it with azure.workload.identity/client-id = workload_client_id).
# ------------------------------------------------------------------------------
resource "azurerm_user_assigned_identity" "workload" {
  name                = "${var.cluster_name}-workload"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "workload" {
  name                = "${var.cluster_name}-${var.workload_namespace}-${var.workload_service_account}"
  resource_group_name = var.resource_group_name
  parent_id           = azurerm_user_assigned_identity.workload.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = azurerm_kubernetes_cluster.this.oidc_issuer_url
  subject             = "system:serviceaccount:${var.workload_namespace}:${var.workload_service_account}"
}

# Let the kubelet pull from ACR.
resource "azurerm_role_assignment" "acr_pull" {
  count                            = var.acr_id == null ? 0 : 1
  scope                            = var.acr_id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}
