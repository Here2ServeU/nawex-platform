# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Instantiates the Azure footprint (AKS + VNet) for the web-app Control Plane.
# Strategy:    Uses AKS Standard Tier for Uptime SLA (Financial Backing).
# ------------------------------------------------------------------------------
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
}
provider "azurerm" {
  features {}
  # Principal Note: Prevent accidental deletion of stateful prod resources
  storage_use_azuread = true
}
# 1. Governance Container (Resource Group)
resource "azurerm_resource_group" "main" {
  name     = "web-app-dev-rg"
  location = var.location
  tags     = var.tags
}
# 2. Network Layer (The VNet)
# Utilizing the Azure Verified Module for best practices
module "vnet" {
  source  = "Azure/vnet/azurerm"
  version = "4.1.0"
  resource_group_name = azurerm_resource_group.main.name
  vnet_name           = "web-app-dev-vnet"
  vnet_location       = azurerm_resource_group.main.location
  use_for_each        = true
  address_space       = ["10.0.0.0/16"]
  subnet_prefixes     = ["10.0.1.0/24", "10.0.2.0/24"]
  subnet_names        = ["aks-subnet", "app-gateway-subnet"]
  tags = var.tags
}
# 3. Compute Layer (AKS Cluster)
# Consuming our proprietary internal module for standardization
module "aks_cluster" {
  source = "../../../modules/compute/azure-aks"
  cluster_name        = "web-app-dev-aks-01"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  k8s_version         = var.k8s_version
  # Networking
  vnet_subnet_id = module.vnet.vnet_subnets[0]
  # Principal Choice: Azure CNI for advanced networking (Pod IPs from VNet)
  network_plugin = "azure"
  # FinOps: System nodes on Pay-As-You-Go, Workload nodes on Spot
  enable_spot_instances = true
  tags = var.tags
}
