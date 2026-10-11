# ------------------------------------------------------------------------------
# AZURE CONTAINER REGISTRY MODULE
# ------------------------------------------------------------------------------
# Private ACR (admin user disabled; AKS pulls with its kubelet identity).
# Images are pushed as <login_server>/<project>/<image>.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

resource "random_string" "suffix" {
  length  = 5
  special = false
  upper   = false
  numeric = true
}

resource "azurerm_container_registry" "acr" {
  # ACR names: 5-50 alphanumerics, globally unique.
  name                = substr("${replace(var.project, "/[^a-z0-9]/", "")}${var.environment}acr${random_string.suffix.result}", 0, 50)
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = var.sku
  admin_enabled       = false
  tags                = var.tags
}
