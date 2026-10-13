variable "name" {
  description = "Base name, e.g. golden-eus -> golden-eus-hub, golden-eus-fw."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Existing resource group for the network resources (connectivity subscription)."
  type        = string
}

variable "hub_address_space" {
  description = "Hub VNet address space."
  type        = list(string)
  default     = ["10.100.0.0/22"]
}

variable "hub_subnets" {
  description = "Hub subnet prefixes. Azure requires AzureFirewallSubnet >= /26, GatewaySubnet >= /27 (/27 recommended), AzureBastionSubnet >= /26."
  type = object({
    firewall          = string
    gateway           = string
    bastion           = string
    private_endpoints = string
  })
  default = {
    firewall          = "10.100.0.0/26"
    gateway           = "10.100.0.64/27"
    bastion           = "10.100.0.128/26"
    private_endpoints = "10.100.1.0/24"
  }
}

variable "spokes" {
  description = "Spoke VNets: name -> address space, segment label (prod/nonprod/shared), subnets (name -> prefixes), use_remote_gateways."
  type = map(object({
    address_space       = list(string)
    segment             = string
    subnets             = map(list(string))
    use_remote_gateways = optional(bool, false)
  }))
  default = {}

  validation {
    condition     = alltrue([for s in values(var.spokes) : contains(["prod", "nonprod", "shared"], s.segment)])
    error_message = "spokes[*].segment must be prod, nonprod or shared."
  }
}

variable "hub_gateway_transit" {
  description = "allow_gateway_transit on hub->spoke peerings (set true once an ExpressRoute/VPN gateway exists in GatewaySubnet)."
  type        = bool
  default     = false
}

variable "firewall_enabled" {
  description = "Deploy Azure Firewall + policy and force spoke traffic through it with UDRs."
  type        = bool
  default     = true
}

variable "firewall_sku_tier" {
  description = "Azure Firewall / policy tier: Standard or Premium (TLS inspection, IDPS)."
  type        = string
  default     = "Standard"

  validation {
    condition     = contains(["Standard", "Premium"], var.firewall_sku_tier)
    error_message = "firewall_sku_tier must be Standard or Premium."
  }
}

variable "allowed_egress_fqdns" {
  description = "FQDNs spokes may reach over HTTPS through the firewall; everything else is denied."
  type        = list(string)
  default     = []
}

variable "dns_servers" {
  description = "Upstream DNS servers for the firewall DNS proxy (empty = Azure DNS)."
  type        = list(string)
  default     = []
}

variable "bastion_enabled" {
  description = "Deploy Azure Bastion (browser RDP/SSH without public IPs on VMs)."
  type        = bool
  default     = false
}

variable "zones" {
  description = "Availability zones for the firewall and its public IP."
  type        = list(string)
  default     = ["1", "2", "3"]
}

variable "private_dns_zones" {
  description = "Private Link DNS zones created and linked to the hub and every spoke."
  type        = list(string)
  default = [
    "privatelink.blob.core.windows.net",
    "privatelink.vaultcore.azure.net",
    "privatelink.azurecr.io",
    "privatelink.database.windows.net",
    "privatelink.servicebus.windows.net",
  ]
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
