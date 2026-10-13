terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.90"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.47"
    }
  }
}

# Run as an identity with Management Group Contributor, Resource Policy Contributor and
# User Access Administrator at the tenant root group, plus Entra Directory Readers
# (to look up groups) and Privileged Role Administrator (PIM policies). The provider
# needs a subscription for its own API calls; ARM_SUBSCRIPTION_ID is the platform
# management subscription.
provider "azurerm" {
  features {}
}

provider "azuread" {}
