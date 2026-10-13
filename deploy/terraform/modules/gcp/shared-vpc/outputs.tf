output "network_id" {
  description = "Shared VPC network ID."
  value       = google_compute_network.this.id
}

output "network_self_link" {
  description = "Shared VPC network self link (GKE `network`)."
  value       = google_compute_network.this.self_link
}

output "subnet_self_links" {
  description = "Subnet name -> self link (GKE `subnetwork`)."
  value       = { for k, s in google_compute_subnetwork.this : k => s.self_link }
}

output "secondary_range_names" {
  description = "Subnet name -> secondary range names (GKE ip_allocation_policy cluster/services range names)."
  value       = { for k, s in var.subnets : k => keys(s.secondary_ranges) }
}

output "router_names" {
  description = "Region -> Cloud Router name (attach Interconnect VLANs / HA VPN here)."
  value       = { for k, r in google_compute_router.this : k => r.name }
}

output "psc_address" {
  description = "Private Service Connect endpoint IP for Google APIs (null when disabled)."
  value       = try(google_compute_global_address.psc[0].address, null)
}
