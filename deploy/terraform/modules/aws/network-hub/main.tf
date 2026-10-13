# ------------------------------------------------------------------------------
# AWS NETWORK HUB MODULE (Transit Gateway + hybrid DNS + Direct Connect)
# ------------------------------------------------------------------------------
# Run once per region in the network account. The Transit Gateway is shared to
# the organization (or selected OUs) with AWS RAM; workload accounts create their
# own VPC attachments, and this module places each attachment in a segment.
#
#   Segments / TGW route tables (default association + propagation DISABLED, so
#   nothing is reachable until this module says so):
#
#     segment     associated with            learns routes from (propagation)
#     prod        prod VPC attachments       shared, hybrid
#     nonprod     nonprod VPC attachments    shared, hybrid
#     shared      shared-services, DX        prod, nonprod, shared, hybrid
#     inspection  inspection VPC             everything
#
#   prod and nonprod never propagate into each other's route table, and each
#   carries BLACKHOLE routes for the other's summary CIDRs (segment_cidrs), so a
#   stray static route or the inspection default route cannot leak between them.
#   Both reach shared services; shared services reach both.
#
#   inspection_enabled      adds 0.0.0.0/0 (and ::/0) -> inspection attachment in
#                           prod/nonprod (north-south through the firewall). The
#                           attachment runs in appliance mode so both directions
#                           of a flow use the same AZ (stateful firewalls).
#   inspect_east_west       also hairpins prod/nonprod <-> shared through the
#                           firewall: spokes only propagate into the inspection
#                           table and every segment default-routes to it.
#
#   Hybrid DNS: Route 53 Resolver inbound (on-prem -> AWS private zones) and
#   outbound endpoints (AWS -> on-prem) in the shared-services VPC. Forwarding
#   rules for on-prem domains are shared to the org with RAM; spoke accounts
#   associate them with their VPCs.
#
#   Direct Connect (optional): a DX gateway associated with the TGW; the DX
#   attachment sits in the shared table and propagates on-prem prefixes into
#   prod, nonprod and shared.
#
# The address plan behind segment_cidrs comes from golden.network.cidr
# (`golden network plan`), and golden.network.reachability models this exact
# design to prove the segmentation intent; see docs/networking/README.md.
# ------------------------------------------------------------------------------

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  east_west = var.inspection_enabled && var.inspect_east_west

  # Which route tables each segment's attachments propagate their CIDRs into.
  propagate_to = {
    prod       = local.east_west ? ["inspection"] : ["shared", "inspection"]
    nonprod    = local.east_west ? ["inspection"] : ["shared", "inspection"]
    shared     = local.east_west ? ["shared", "inspection"] : ["prod", "nonprod", "shared", "inspection"]
    hybrid     = local.east_west ? ["inspection"] : ["prod", "nonprod", "shared", "inspection"]
    inspection = []
  }

  # Which route table each segment's attachments are associated with.
  associate_with = {
    prod       = "prod"
    nonprod    = "nonprod"
    shared     = "shared"
    hybrid     = "shared"
    inspection = "inspection"
  }

  route_tables = toset(["prod", "nonprod", "shared", "inspection"])

  attachment_segments = merge(
    { for k, a in var.spoke_attachments : k => a.segment },
    { "shared-services" = "shared" },
    var.inspection_enabled ? { inspection = "inspection" } : {},
    var.direct_connect_enabled ? { "direct-connect" = "hybrid" } : {},
  )

  attachment_ids = merge(
    { for k, a in var.spoke_attachments : k => a.attachment_id },
    { "shared-services" = aws_ec2_transit_gateway_vpc_attachment.shared_services.id },
    var.inspection_enabled ? { inspection = aws_ec2_transit_gateway_vpc_attachment.inspection[0].id } : {},
    var.direct_connect_enabled ? { "direct-connect" = data.aws_ec2_transit_gateway_dx_gateway_attachment.dx[0].id } : {},
  )

  propagations = merge([
    for name, segment in local.attachment_segments : {
      for rt in local.propagate_to[segment] : "${name}|${rt}" => { attachment = name, route_table = rt }
    }
  ]...)

  default_cidrs = var.enable_ipv6 ? ["0.0.0.0/0", "::/0"] : ["0.0.0.0/0"]
  inspected_tables = !var.inspection_enabled ? [] : (
    local.east_west ? ["prod", "nonprod", "shared"] : ["prod", "nonprod"]
  )
  default_routes = {
    for pair in setproduct(local.inspected_tables, local.default_cidrs) : "${pair[0]}|${pair[1]}" => {
      route_table = pair[0]
      cidr        = pair[1]
    }
  }

  # prod blackholes nonprod's summaries and vice versa.
  blackholes = merge(
    { for c in lookup(var.segment_cidrs, "nonprod", []) : "prod|${c}" => { route_table = "prod", cidr = c } },
    { for c in lookup(var.segment_cidrs, "prod", []) : "nonprod|${c}" => { route_table = "nonprod", cidr = c } },
  )

  ipv6_support = var.enable_ipv6 ? "enable" : "disable"
}

# ----------------------------------------------------------------------------- transit gateway
resource "aws_ec2_transit_gateway" "this" {
  description                     = "${var.name} hub (${data.aws_region.current.name})"
  amazon_side_asn                 = var.amazon_side_asn
  default_route_table_association = "disable"
  default_route_table_propagation = "disable"
  auto_accept_shared_attachments  = var.auto_accept_shared_attachments ? "enable" : "disable"
  dns_support                     = "enable"
  vpn_ecmp_support                = "enable"
  multicast_support               = "disable"
  transit_gateway_cidr_blocks     = var.transit_gateway_cidr_blocks

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_ec2_transit_gateway_route_table" "this" {
  for_each = local.route_tables

  transit_gateway_id = aws_ec2_transit_gateway.this.id
  tags               = merge(var.tags, { Name = "${var.name}-${each.key}", Segment = each.key })
}

# ----------------------------------------------------------------------------- attachments owned here
resource "aws_ec2_transit_gateway_vpc_attachment" "shared_services" {
  transit_gateway_id                              = aws_ec2_transit_gateway.this.id
  vpc_id                                          = var.shared_services_vpc.vpc_id
  subnet_ids                                      = var.shared_services_vpc.tgw_subnet_ids
  ipv6_support                                    = local.ipv6_support
  dns_support                                     = "enable"
  transit_gateway_default_route_table_association = false
  transit_gateway_default_route_table_propagation = false

  tags = merge(var.tags, { Name = "${var.name}-shared-services", Segment = "shared" })
}

resource "aws_ec2_transit_gateway_vpc_attachment" "inspection" {
  count = var.inspection_enabled ? 1 : 0

  transit_gateway_id                              = aws_ec2_transit_gateway.this.id
  vpc_id                                          = var.inspection_vpc.vpc_id
  subnet_ids                                      = var.inspection_vpc.tgw_subnet_ids
  appliance_mode_support                          = "enable"
  ipv6_support                                    = local.ipv6_support
  transit_gateway_default_route_table_association = false
  transit_gateway_default_route_table_propagation = false

  tags = merge(var.tags, { Name = "${var.name}-inspection", Segment = "inspection" })

  lifecycle {
    precondition {
      condition     = var.inspection_vpc != null
      error_message = "inspection_enabled = true requires inspection_vpc."
    }
  }
}

# ----------------------------------------------------------------------------- segmentation
resource "aws_ec2_transit_gateway_route_table_association" "this" {
  for_each = local.attachment_segments

  transit_gateway_attachment_id  = local.attachment_ids[each.key]
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.this[local.associate_with[each.value]].id
}

resource "aws_ec2_transit_gateway_route_table_propagation" "this" {
  for_each = local.propagations

  transit_gateway_attachment_id  = local.attachment_ids[each.value.attachment]
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.this[each.value.route_table].id
}

resource "aws_ec2_transit_gateway_route" "default_to_inspection" {
  for_each = local.default_routes

  destination_cidr_block         = each.value.cidr
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.inspection[0].id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.this[each.value.route_table].id
}

resource "aws_ec2_transit_gateway_route" "blackhole" {
  for_each = local.blackholes

  destination_cidr_block         = each.value.cidr
  blackhole                      = true
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.this[each.value.route_table].id
}

# ----------------------------------------------------------------------------- RAM share to the org / OUs
resource "aws_ram_resource_share" "tgw" {
  name                      = "${var.name}-tgw"
  allow_external_principals = false
  tags                      = var.tags
}

resource "aws_ram_resource_association" "tgw" {
  resource_arn       = aws_ec2_transit_gateway.this.arn
  resource_share_arn = aws_ram_resource_share.tgw.arn
}

resource "aws_ram_principal_association" "tgw" {
  for_each = toset(var.ram_principals)

  principal          = each.value
  resource_share_arn = aws_ram_resource_share.tgw.arn
}

# ----------------------------------------------------------------------------- TGW flow logs
resource "aws_cloudwatch_log_group" "flow_logs" {
  count = var.flow_log_s3_arn == null ? 1 : 0

  name              = "/golden/network/${var.name}/tgw-flow-logs"
  retention_in_days = var.flow_log_retention_days
  kms_key_id        = var.flow_log_kms_key_arn
  tags              = var.tags
}

data "aws_iam_policy_document" "flow_logs_assume" {
  count = var.flow_log_s3_arn == null ? 1 : 0

  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["vpc-flow-logs.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "flow_logs_write" {
  count = var.flow_log_s3_arn == null ? 1 : 0

  statement {
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = ["${aws_cloudwatch_log_group.flow_logs[0].arn}:*"]
  }
}

resource "aws_iam_role" "flow_logs" {
  count = var.flow_log_s3_arn == null ? 1 : 0

  name                 = "${var.name}-tgw-flow-logs"
  assume_role_policy   = data.aws_iam_policy_document.flow_logs_assume[0].json
  permissions_boundary = var.permissions_boundary_arn
  tags                 = var.tags
}

resource "aws_iam_role_policy" "flow_logs" {
  count = var.flow_log_s3_arn == null ? 1 : 0

  name   = "write-tgw-flow-logs"
  role   = aws_iam_role.flow_logs[0].id
  policy = data.aws_iam_policy_document.flow_logs_write[0].json
}

resource "aws_flow_log" "tgw" {
  transit_gateway_id       = aws_ec2_transit_gateway.this.id
  max_aggregation_interval = 60
  log_destination_type     = var.flow_log_s3_arn == null ? "cloud-watch-logs" : "s3"
  log_destination          = var.flow_log_s3_arn == null ? aws_cloudwatch_log_group.flow_logs[0].arn : var.flow_log_s3_arn
  iam_role_arn             = var.flow_log_s3_arn == null ? aws_iam_role.flow_logs[0].arn : null

  tags = merge(var.tags, { Name = "${var.name}-tgw" })
}

# ----------------------------------------------------------------------------- hybrid DNS (Route 53 Resolver)
resource "aws_security_group" "resolver" {
  count = var.resolver_enabled ? 1 : 0

  name        = "${var.name}-resolver"
  description = "Route 53 Resolver endpoints: DNS from the org and on-prem"
  vpc_id      = var.shared_services_vpc.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-resolver" })
}

resource "aws_vpc_security_group_ingress_rule" "resolver" {
  for_each = var.resolver_enabled ? {
    for pair in setproduct(["tcp", "udp"], var.dns_client_cidrs) : "${pair[0]}|${pair[1]}" => pair
  } : {}

  security_group_id = aws_security_group.resolver[0].id
  description       = "DNS (${each.value[0]}) from ${each.value[1]}"
  ip_protocol       = each.value[0]
  from_port         = 53
  to_port           = 53
  cidr_ipv4         = can(cidrnetmask(each.value[1])) ? each.value[1] : null
  cidr_ipv6         = can(cidrnetmask(each.value[1])) ? null : each.value[1]
}

resource "aws_vpc_security_group_egress_rule" "resolver" {
  for_each = var.resolver_enabled ? {
    for pair in setproduct(["tcp", "udp"], var.onprem_dns_cidrs) : "${pair[0]}|${pair[1]}" => pair
  } : {}

  security_group_id = aws_security_group.resolver[0].id
  description       = "DNS (${each.value[0]}) to on-prem resolvers ${each.value[1]}"
  ip_protocol       = each.value[0]
  from_port         = 53
  to_port           = 53
  cidr_ipv4         = each.value[1]
}

resource "aws_route53_resolver_endpoint" "inbound" {
  count = var.resolver_enabled ? 1 : 0

  name                   = "${var.name}-inbound"
  direction              = "INBOUND"
  resolver_endpoint_type = var.enable_ipv6 ? "DUALSTACK" : "IPV4"
  security_group_ids     = [aws_security_group.resolver[0].id]

  dynamic "ip_address" {
    for_each = var.shared_services_vpc.resolver_subnet_ids
    content {
      subnet_id = ip_address.value
    }
  }

  tags = var.tags
}

resource "aws_route53_resolver_endpoint" "outbound" {
  count = var.resolver_enabled ? 1 : 0

  name                   = "${var.name}-outbound"
  direction              = "OUTBOUND"
  resolver_endpoint_type = var.enable_ipv6 ? "DUALSTACK" : "IPV4"
  security_group_ids     = [aws_security_group.resolver[0].id]

  dynamic "ip_address" {
    for_each = var.shared_services_vpc.resolver_subnet_ids
    content {
      subnet_id = ip_address.value
    }
  }

  tags = var.tags
}

resource "aws_route53_resolver_rule" "forward" {
  for_each = var.resolver_enabled ? var.onprem_forward_domains : {}

  name                 = "${var.name}-${replace(each.key, ".", "-")}"
  domain_name          = each.key
  rule_type            = "FORWARD"
  resolver_endpoint_id = aws_route53_resolver_endpoint.outbound[0].id

  dynamic "target_ip" {
    for_each = each.value
    content {
      ip   = target_ip.value
      port = 53
    }
  }

  tags = var.tags
}

resource "aws_route53_resolver_rule_association" "shared_services" {
  for_each = aws_route53_resolver_rule.forward

  resolver_rule_id = each.value.id
  vpc_id           = var.shared_services_vpc.vpc_id
}

resource "aws_ram_resource_share" "resolver_rules" {
  count = var.resolver_enabled && length(var.onprem_forward_domains) > 0 ? 1 : 0

  name                      = "${var.name}-resolver-rules"
  allow_external_principals = false
  tags                      = var.tags
}

resource "aws_ram_resource_association" "resolver_rules" {
  for_each = length(aws_ram_resource_share.resolver_rules) > 0 ? aws_route53_resolver_rule.forward : {}

  resource_arn       = each.value.arn
  resource_share_arn = aws_ram_resource_share.resolver_rules[0].arn
}

resource "aws_ram_principal_association" "resolver_rules" {
  for_each = length(aws_ram_resource_share.resolver_rules) > 0 ? toset(var.ram_principals) : toset([])

  principal          = each.value
  resource_share_arn = aws_ram_resource_share.resolver_rules[0].arn
}

# ----------------------------------------------------------------------------- Direct Connect (optional)
resource "aws_dx_gateway" "this" {
  count = var.direct_connect_enabled ? 1 : 0

  name            = "${var.name}-dxgw"
  amazon_side_asn = tostring(var.direct_connect_amazon_side_asn)
}

resource "aws_dx_gateway_association" "tgw" {
  count = var.direct_connect_enabled ? 1 : 0

  dx_gateway_id         = aws_dx_gateway.this[0].id
  associated_gateway_id = aws_ec2_transit_gateway.this.id
  # Prefixes advertised TO on-prem over BGP: the AWS summaries, not every VPC.
  allowed_prefixes = var.direct_connect_allowed_prefixes
}

data "aws_ec2_transit_gateway_dx_gateway_attachment" "dx" {
  count = var.direct_connect_enabled ? 1 : 0

  transit_gateway_id = aws_ec2_transit_gateway.this.id
  dx_gateway_id      = aws_dx_gateway.this[0].id

  depends_on = [aws_dx_gateway_association.tgw]
}
