output "vms" {
  description = "Per-VM sizing and placement facts for wave planning."
  value = {
    for name, vm in data.vsphere_virtual_machine.vm : name => {
      id               = vm.id
      uuid             = vm.uuid
      guest_id         = vm.guest_id
      firmware         = vm.firmware
      num_cpus         = vm.num_cpus
      memory_mb        = vm.memory
      disk_sizes_gb    = [for d in vm.disks : d.size]
      network_ids      = vm.network_interfaces[*].network_id
      tools_status     = vm.vmware_tools_status
      total_disk_gb    = sum(concat([0], [for d in vm.disks : d.size]))
      guest_ip_address = vm.guest_ip_addresses
    }
  }
}

output "datastore_ids" {
  value = { for k, v in data.vsphere_datastore.ds : k => v.id }
}

output "network_ids" {
  value = { for k, v in data.vsphere_network.net : k => v.id }
}
