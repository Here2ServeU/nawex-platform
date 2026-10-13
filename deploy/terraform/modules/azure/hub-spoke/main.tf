# ------------------------------------------------------------------------------
# AZURE HUB-SPOKE MODULE (hub VNet, Azure Firewall, spokes, private DNS)
# ------------------------------------------------------------------------------
# The Azure equivalent of the AWS network-hub module:
#
#   hub VNet          AzureFirewallSubnet (/26), GatewaySubnet (/27, for an
#                     ExpressRoute / VPN gateway), AzureBastionSubnet (/26) and a
#                     private-endpoints subnet. Subnet names are fixed by Azure.
#   Azure Firewall    optional, with a Firewall Policy: threat intel = Deny, DNS
#                     proxy on, spoke -> hub allowed, egress only to allowed FQDNs.
#                     Everything else (including prod <-> nonprod) is denied by
#                     the firewall's default deny.
#   spokes            VNets from a map, each with a segment label.
#   peerings          hub <-> spoke in both directions. VNet peering is NOT
#                     transitive, so spoke-to-spoke traffic has to go through the
#                     firewall; that is what makes the firewall the segmentation
#                     point. allow_gateway_transit on the hub side and optional
#                     use_remote_gateways on the spoke side share the hub's
#                     ExpressRoute/VPN gateway with spokes.
#   UDRs              every spoke subnet: 0.0.0.0/0 -> firewall private IP, BGP
#                     route propagation off so on-prem routes learned by the
#                     gateway cannot bypass the firewall.
#   private DNS       privatelink.* zones linked to the hub and every spoke so
#                     Private Endpoints resolve to private IPs everywhere.
#
# See docs/networking/README.md for how this maps to TGW segments on AWS.
# ------------------------------------------------------------------------------

locals {
  spoke_subnets = merge([
    for spoke, s in var.spokes : {
      for subnet, prefixes in s.subnets : "${spoke}|${subnet}" => {
        spoke            = spoke
        name             = subnet
        address_prefixes = prefixes
      }
    }
  ]...)

  vnet_ids = merge(
    { hub = azurerm_virtual_network.hub.id },
    { for k, v in azurerm_virtual_network.spoke : k => v.id },
  )

  dns_links = {
    for pair in setproduct(var.private_dns_zones, concat(["hub"], keys(var.spokes))) :
    "${pair[0]}|${pair[1]}" => { zone = pair[0], vnet = pair[1] }
  }

  spoke_cidrs = flatten([for s in values(var.spokes) : s.address_space])
}

# ----------------------------------------------------------------------------- hub
resource "azurerm_virtual_network" "hub" {
  name                = "${var.name}-hub"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.hub_address_space
  tags                = var.tags
}

# Separate resource: the firewall lives inside the hub VNet, so setting dns_servers
# on the VNet itself would be a dependency cycle.
resource "azurerm_virtual_network_dns_servers" "hub" {
  count = var.firewall_enabled || length(var.dns_servers) > 0 ? 1 : 0

  virtual_network_id = azurerm_virtual_network.hub.id
  dns_servers        = var.firewall_enabled ? [azurerm_firewall.hub[0].ip_configuration[0].private_ip_address] : var.dns_servers
}

resource "azurerm_subnet" "firewall" {
  name                 = "AzureFirewallSubnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [var.hub_subnets.firewall]
}

resource "azurerm_subnet" "gateway" {
  name                 = "GatewaySubnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [var.hub_subnets.gateway]
}

resource "azurerm_subnet" "bastion" {
  name                 = "AzureBastionSubnet"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [var.hub_subnets.bastion]
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [var.hub_subnets.private_endpoints]
}

# ----------------------------------------------------------------------------- Azure Firewall (optional)
resource "azurerm_public_ip" "firewall" {
  count = var.firewall_enabled ? 1 : 0

  name                = "${var.name}-fw-pip"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  zones               = var.zones
  tags                = var.tags
}

resource "azurerm_firewall_policy" "hub" {
  count = var.firewall_enabled ? 1 : 0

  name                     = "${var.name}-fw-policy"
  location                 = var.location
  resource_group_name      = var.resource_group_name
  sku                      = var.firewall_sku_tier
  threat_intelligence_mode = "Deny"

  dns {
    proxy_enabled = true
    servers       = var.dns_servers
  }

  tags = var.tags
}

resource "azurerm_firewall_policy_rule_collection_group" "baseline" {
  count = var.firewall_enabled ? 1 : 0

  name               = "baseline"
  firewall_policy_id = azurerm_firewall_policy.hub[0].id
  priority           = 200

  network_rule_collection {
    name     = "spokes-to-hub"
    priority = 200
    action   = "Allow"

    rule {
      name                  = "spokes-to-shared-services"
      protocols             = ["TCP", "UDP", "ICMP"]
      source_addresses      = local.spoke_cidrs
      destination_addresses = var.hub_address_space
      destination_ports     = ["*"]
    }
  }

  dynamic "application_rule_collection" {
    for_each = length(var.allowed_egress_fqdns) > 0 ? [1] : []
    content {
      name     = "egress-allowlist"
      priority = 300
      action   = "Allow"

      rule {
        name              = "allowed-fqdns"
        source_addresses  = local.spoke_cidrs
        destination_fqdns = var.allowed_egress_fqdns

        protocols {
          type = "Https"
          port = 443
        }
      }
    }
  }
}

resource "azurerm_firewall" "hub" {
  count = var.firewall_enabled ? 1 : 0

  name                = "${var.name}-fw"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = "AZFW_VNet"
  sku_tier            = var.firewall_sku_tier
  firewall_policy_id  = azurerm_firewall_policy.hub[0].id
  zones               = var.zones

  ip_configuration {
    name                 = "ipconfig"
    subnet_id            = azurerm_subnet.firewall.id
    public_ip_address_id = azurerm_public_ip.firewall[0].id
  }

  tags = var.tags
}

# ----------------------------------------------------------------------------- Bastion (optional)
resource "azurerm_public_ip" "bastion" {
  count = var.bastion_enabled ? 1 : 0

  name                = "${var.name}-bastion-pip"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_bastion_host" "hub" {
  count = var.bastion_enabled ? 1 : 0

  name                = "${var.name}-bastion"
  location            = var.location
  resource_group_name = var.resource_group_name

  ip_configuration {
    name                 = "ipconfig"
    subnet_id            = azurerm_subnet.bastion.id
    public_ip_address_id = azurerm_public_ip.bastion[0].id
  }

  tags = var.tags
}

# ----------------------------------------------------------------------------- spokes
resource "azurerm_virtual_network" "spoke" {
  for_each = var.spokes

  name                = "${var.name}-${each.key}"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = each.value.address_space
  # Spokes resolve through the firewall DNS proxy (or the given DNS servers).
  dns_servers = var.firewall_enabled ? [azurerm_firewall.hub[0].ip_configuration[0].private_ip_address] : var.dns_servers
  tags        = merge(var.tags, { segment = each.value.segment })
}

resource "azurerm_subnet" "spoke" {
  for_each = local.spoke_subnets

  name                 = each.value.name
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.spoke[each.value.spoke].name
  address_prefixes     = each.value.address_prefixes
}

resource "azurerm_virtual_network_peering" "hub_to_spoke" {
  for_each = var.spokes

  name                         = "hub-to-${each.key}"
  resource_group_name          = var.resource_group_name
  virtual_network_name         = azurerm_virtual_network.hub.name
  remote_virtual_network_id    = azurerm_virtual_network.spoke[each.key].id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
  allow_gateway_transit        = var.hub_gateway_transit
}

resource "azurerm_virtual_network_peering" "spoke_to_hub" {
  for_each = var.spokes

  name                         = "${each.key}-to-hub"
  resource_group_name          = var.resource_group_name
  virtual_network_name         = azurerm_virtual_network.spoke[each.key].name
  remote_virtual_network_id    = azurerm_virtual_network.hub.id
  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
  # Requires an ExpressRoute/VPN gateway in the hub's GatewaySubnet.
  use_remote_gateways = each.value.use_remote_gateways

  depends_on = [azurerm_virtual_network_peering.hub_to_spoke]
}

# ----------------------------------------------------------------------------- UDR -> firewall
resource "azurerm_route_table" "spoke" {
  for_each = var.firewall_enabled ? var.spokes : {}

  name                = "${var.name}-${each.key}-rt"
  location            = var.location
  resource_group_name = var.resource_group_name
  # Newer 3.x releases spell this bgp_route_propagation_enabled = false; this form works across ~> 3.90.
  disable_bgp_route_propagation = true

  route {
    name                   = "default-via-firewall"
    address_prefix         = "0.0.0.0/0"
    next_hop_type          = "VirtualAppliance"
    next_hop_in_ip_address = azurerm_firewall.hub[0].ip_configuration[0].private_ip_address
  }

  tags = var.tags
}

resource "azurerm_subnet_route_table_association" "spoke" {
  for_each = var.firewall_enabled ? local.spoke_subnets : {}

  subnet_id      = azurerm_subnet.spoke[each.key].id
  route_table_id = azurerm_route_table.spoke[each.value.spoke].id
}

# ----------------------------------------------------------------------------- private DNS (Private Endpoints)
resource "azurerm_private_dns_zone" "this" {
  for_each = toset(var.private_dns_zones)

  name                = each.value
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "this" {
  for_each = local.dns_links

  name                  = "${each.value.vnet}-${replace(each.value.zone, ".", "-")}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.this[each.value.zone].name
  virtual_network_id    = local.vnet_ids[each.value.vnet]
  registration_enabled  = false
  tags                  = var.tags
}
