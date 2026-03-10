# ------------------------------------------------------------------------------
# AZURE CONTAINER REGISTRY (SHARED)
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Provisions the central artifact store for all environments.
# Strategy:    Decoupled from cluster lifecycle to prevent accidental image deletion.
# ------------------------------------------------------------------------------

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
  }
  # Principal Note: Use the bootstrap backend we created earlier
  # backend "azurerm" {
  #   ...
  # }
}

provider "azurerm" {
  features {}
}

# 1. Governance Container
resource "azurerm_resource_group" "registry" {
  name     = "express-web-registry-rg"
  location = var.location
  tags     = var.tags
}

# 2. Container Registry (The Artifact Store)
resource "azurerm_container_registry" "acr" {
  name                = "expresswebacr${random_string.suffix.result}" # Globally unique
  resource_group_name = azurerm_resource_group.registry.name
  location            = azurerm_resource_group.registry.location
  
  # Principal Choice: Standard Tier allows for higher throughput (100MBps)
  # Basic Tier thottles heavily during concurrent deployments.
  sku                 = "Standard"
  
  # Security: Disable legacy admin username/password access.
  # We use AD Managed Identity for AKS pulls.
  admin_enabled       = false

  tags = var.tags
}

resource "random_string" "suffix" {
  length  = 4
  special = false
  upper   = false
  numeric = true
}

# 3. (Optional) Vulnerability Scanning
# In a Premium registry, you would enable retention policies and trust here.
