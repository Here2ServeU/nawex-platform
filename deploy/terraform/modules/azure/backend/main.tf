# ------------------------------------------------------------------------------
# AZURE TERRAFORM BOOTSTRAP
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Provisions the "backend" infrastructure (Storage Account) to
#              store Terraform state files for Dev, Stage, and Prod.
# Strategy:    Enables Versioning and Encryption for Disaster Recovery.
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
}

# 1. Resource Group for Administrative Resources
# This separates the "State" infrastructure from the "Workload" infrastructure.
resource "azurerm_resource_group" "tfstate" {
  name     = "${var.name_prefix}-tfstate-rg"
  location = var.location
  tags     = var.tags
}

# 2. Storage Account (The Vault)
resource "azurerm_storage_account" "tfstate" {
  name                     = "${substr(replace(var.name_prefix, "/[^a-z0-9]/", ""), 0, 12)}tfstate${random_string.suffix.result}" # Must be globally unique
  resource_group_name      = azurerm_resource_group.tfstate.name
  location                 = azurerm_resource_group.tfstate.location
  account_tier             = "Standard"
  account_replication_type = "GRS" # Geo-Redundant Storage for Disaster Recovery

  # Security Hardening
  min_tls_version           = "TLS1_2"
  enable_https_traffic_only = true

  blob_properties {
    versioning_enabled = true # Critical: Allows rollback of corrupted state files
  }

  # Deny by default; allow only the operator / CI egress IPs.
  public_network_access_enabled   = true
  allow_nested_items_to_be_public = false

  network_rules {
    default_action = "Deny"
    bypass         = ["AzureServices"]
    ip_rules       = var.allowed_ips
  }

  tags = var.tags
}

# 3. Random Suffix for Uniqueness
resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
}

# 4. Containers (The Folders)
# We create separate containers for isolation, though folders work too.
resource "azurerm_storage_container" "dev_state" {
  name                  = "tfstate-dev"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "prod_state" {
  name                  = "tfstate-prod"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}

# Single container used by every live/azure/<env> (key = golden/<env>/terraform.tfstate).
resource "azurerm_storage_container" "shared" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.tfstate.name
  container_access_type = "private"
}
