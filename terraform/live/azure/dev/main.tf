terraform {
  required_version = ">= 1.3.0"
  backend "azurerm" {
    resource_group_name  = "rg-terraform-backend"
    storage_account_name = "tfstateaccount11202025"
    container_name       = "tfstate"
    key                  = "azure/dev/terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

# Backend infra would be provisioned separately using azure/backend module.

module "acr" {
  source              = "../../modules/azure/acr"
  acr_name            = "t2sacrdev1120"
  resource_group_name = "rg-aks-dev"
  location            = "eastus"
}

module "aks" {
  source              = "../../modules/azure/aks"
  name                = "t2s-aks-dev"
  resource_group_name = "rg-aks-dev"
  location            = "eastus"
}
