# ------------------------------------------------------------------------------
# vSphere inventory (read-only)
# ------------------------------------------------------------------------------
# Looks up the VMs of one migration wave plus the datastores and networks they
# use, so the MTV NetworkMap / StorageMap / Plan for that wave can be generated
# from facts (see deploy/openshift/virtualization). Creates nothing.
# The vsphere provider is configured by the caller (VSPHERE_SERVER /
# VSPHERE_USER / VSPHERE_PASSWORD environment variables are supported).
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    vsphere = {
      source  = "vmware/vsphere"
      version = "~> 2.10"
    }
  }
}

data "vsphere_datacenter" "this" {
  name = var.datacenter
}

data "vsphere_virtual_machine" "vm" {
  for_each      = toset(var.vm_names)
  name          = each.value
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_datastore" "ds" {
  for_each      = toset(var.datastores)
  name          = each.value
  datacenter_id = data.vsphere_datacenter.this.id
}

data "vsphere_network" "net" {
  for_each      = toset(var.networks)
  name          = each.value
  datacenter_id = data.vsphere_datacenter.this.id
}
