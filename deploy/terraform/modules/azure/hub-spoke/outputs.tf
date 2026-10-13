output "hub_vnet_id" {
  description = "Hub VNet ID."
  value       = azurerm_virtual_network.hub.id
}

output "spoke_vnet_ids" {
  description = "Spoke name -> VNet ID."
  value       = { for k, v in azurerm_virtual_network.spoke : k => v.id }
}

output "spoke_subnet_ids" {
  description = "\"spoke|subnet\" -> subnet ID."
  value       = { for k, s in azurerm_subnet.spoke : k => s.id }
}

output "gateway_subnet_id" {
  description = "GatewaySubnet ID for an ExpressRoute / VPN gateway."
  value       = azurerm_subnet.gateway.id
}

output "private_endpoint_subnet_id" {
  description = "Hub subnet for shared Private Endpoints."
  value       = azurerm_subnet.private_endpoints.id
}

output "firewall_private_ip" {
  description = "Azure Firewall private IP (UDR next hop, DNS proxy). Null when the firewall is disabled."
  value       = try(azurerm_firewall.hub[0].ip_configuration[0].private_ip_address, null)
}

output "firewall_policy_id" {
  description = "Firewall Policy ID, for extra rule collection groups owned by app teams."
  value       = try(azurerm_firewall_policy.hub[0].id, null)
}

output "private_dns_zone_ids" {
  description = "Private DNS zone name -> ID (use in private_dns_zone_group of Private Endpoints)."
  value       = { for k, z in azurerm_private_dns_zone.this : k => z.id }
}
