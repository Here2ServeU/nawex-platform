# ------------------------------------------------------------------------------
# Golden platform landing zone - AZURE / dev
# Generated layout: every live/{aws,azure,gcp}/{dev,staging,prod} directory
# exposes the same inputs (variables.tf) and outputs (outputs.tf).
# ------------------------------------------------------------------------------

locals {
  name = "${var.project}-${var.environment}"
  tags = merge({
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
  }, var.tags)
}

resource "azurerm_resource_group" "this" {
  name     = "${local.name}-rg"
  location = var.region
  tags     = local.tags
}

resource "azurerm_virtual_network" "this" {
  name                = "${local.name}-vnet"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  address_space       = ["10.40.0.0/16"]
  tags                = local.tags
}

resource "azurerm_subnet" "aks" {
  name                 = "aks-nodes"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.40.0.0/20"]
}

module "registry" {
  source              = "../../../modules/azure/registry"
  project             = var.project
  environment         = var.environment
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = var.environment == "prod" ? "Premium" : "Standard"
  tags                = local.tags
}

module "aks" {
  source = "../../../modules/azure/aks"

  cluster_name        = "${local.name}-aks"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  vnet_subnet_id      = azurerm_subnet.aks.id
  kubernetes_version  = var.kubernetes_version
  sku_tier            = var.environment == "prod" ? "Standard" : "Free"

  node_count         = var.node_count
  node_instance_type = var.node_instance_type

  gpu_node_pool_enabled = var.gpu_node_pool_enabled
  gpu_instance_type     = var.gpu_instance_type
  gpu_node_count        = var.gpu_node_count

  acr_id = module.registry.registry_id
  tags   = local.tags

  api_server_authorized_cidrs = var.api_server_authorized_cidrs
}
