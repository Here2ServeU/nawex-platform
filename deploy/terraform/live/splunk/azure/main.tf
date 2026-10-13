terraform {
  required_version = ">= 1.3.0"
}

provider "azurerm" {
  features {}
}

module "splunk" {
  source = "../../../modules/splunk/azure"

  name           = var.name
  location       = var.location
  resource_group = var.resource_group
  subnet_id      = var.subnet_id
  vm_size        = var.vm_size
  ssh_public_key = var.ssh_public_key
  admin_password = var.admin_password
  hec_token      = var.hec_token
}
