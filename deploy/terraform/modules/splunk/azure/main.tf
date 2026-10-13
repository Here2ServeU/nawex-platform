terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 3.0"
    }
  }
}

resource "azurerm_public_ip" "splunk_pip" {
  name                = "${var.name}-pip"
  location            = var.location
  resource_group_name = var.resource_group
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_interface" "splunk_nic" {
  name                = "${var.name}-nic"
  location            = var.location
  resource_group_name = var.resource_group

  ip_configuration {
    name                          = "internal"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.splunk_pip.id
  }
}

resource "azurerm_linux_virtual_machine" "splunk_vm" {
  name                = "${var.name}-vm"
  resource_group_name = var.resource_group
  location            = var.location
  size                = var.vm_size
  admin_username      = "azureuser"
  network_interface_ids = [
    azurerm_network_interface.splunk_nic.id
  ]

  admin_ssh_key {
    username   = "azureuser"
    public_key = file(var.ssh_public_key)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("${path.module}/cloud-init.yaml", {
    admin_password = var.admin_password
    hec_token      = var.hec_token
  }))

  tags = {
    Role = "splunk-enterprise"
  }
}
