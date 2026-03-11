# ------------------------------------------------------------------------------
# EXPRESS WEB AZURE DEV - MAIN ENTRY POINT
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Instantiates the Dev environment using the cost-optimized AKS module.
# Strategy:    East US 2 (Cheaper region), Spot Instances, Free Tier Control Plane.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }

  # Principal Note: Remote State is mandatory for team collaboration.
  # backend "azurerm" {
  #   resource_group_name  = "express-web-tfstate-rg"
  #   storage_account_name = "ewtfstate"
  #   container_name       = "tfstate-dev"
  #   key                  = "express-web.dev.terraform.tfstate"
  # }
}

provider "azurerm" {
  features {}
}

# 1. Governance Container (Resource Group)
resource "azurerm_resource_group" "dev" {
  name     = "express-web-dev-rg"
  location = var.location
  tags     = var.tags
}

# 2. Network Layer (VNet)
# We use a smaller CIDR for Dev to save IP space.
module "vnet" {
  source  = "Azure/vnet/azurerm"
  version = "4.1.0"

  resource_group_name = azurerm_resource_group.dev.name
  vnet_name           = "express-web-dev-vnet"
  vnet_location       = azurerm_resource_group.dev.location
  use_for_each        = true

  address_space       = ["10.10.0.0/16"]
  subnet_prefixes     = ["10.10.1.0/24"]
  subnet_names        = ["aks-subnet"]

  tags = var.tags
}

# 3. Compute Layer (AKS Cluster)
# Consuming the Cost-Optimized Module
module "aks_cluster" {
  source = "../../../modules/compute/azure-aks"

  cluster_name        = "express-web-dev-aks-01"
  resource_group_name = azurerm_resource_group.dev.name
  location            = azurerm_resource_group.dev.location
  
  # Networking
  vnet_subnet_id = module.vnet.vnet_subnets[0]
  
  # Principal FinOps: Explicitly enabling Spot instances for Dev
  enable_spot_instances = true

  tags = var.tags
}
