# ------------------------------------------------------------------------------
# Golden platform — AWS network hub (network account, one root per region)
#
# Applied from the network account after the org stack (live/aws/org), and
# before the workload landing zones in live/aws/{dev,staging,prod} attach:
#
#   network_hub        Transit Gateway with prod / nonprod / shared / inspection
#                      route tables, RAM share to the org, TGW flow logs, Route 53
#                      Resolver hybrid DNS, optional inspection VPC and Direct
#                      Connect gateway (modules/aws/network-hub)
#   shared_endpoints   PrivateLink + gateway endpoints in the shared-services VPC
#                      with org-only endpoint policies (modules/aws/vpc-endpoints)
#
# Address plan: `golden network plan` (src/golden/network/cidr.py) produces the
# VPC CIDRs and the segment summaries used for segment_cidrs below.
# Segmentation proof: `golden network verify` (src/golden/network/reachability.py)
# models this design and checks prod <-> nonprod is denied, both -> shared allowed.
# Plans are gated by security/policies/opa/network.rego and aws-iam.rego.
#
#   terraform init -backend-config=backend.hcl
#   terraform plan -out tf.plan && terraform show -json tf.plan > plan.json
#   opa eval -d security/policies/opa -i plan.json 'data.golden.network.deny'
# ------------------------------------------------------------------------------

locals {
  tags = merge({
    Project   = var.project
    Scope     = "network"
    ManagedBy = "terraform"
  }, var.tags)
}

module "network_hub" {
  source = "../../../modules/aws/network-hub"

  name            = "${var.project}-${var.region_code}-hub"
  amazon_side_asn = var.tgw_asn
  enable_ipv6     = var.enable_ipv6
  ram_principals  = var.ram_principals

  shared_services_vpc = var.shared_services_vpc
  spoke_attachments   = var.spoke_attachments
  segment_cidrs       = var.segment_cidrs

  inspection_enabled = var.inspection_vpc != null
  inspect_east_west  = var.inspect_east_west
  inspection_vpc     = var.inspection_vpc

  flow_log_s3_arn          = var.flow_log_s3_arn
  permissions_boundary_arn = var.permissions_boundary_arn

  dns_client_cidrs       = var.dns_client_cidrs
  onprem_dns_cidrs       = var.onprem_dns_cidrs
  onprem_forward_domains = var.onprem_forward_domains

  direct_connect_enabled          = var.direct_connect_enabled
  direct_connect_allowed_prefixes = var.direct_connect_allowed_prefixes

  tags = local.tags
}

module "shared_endpoints" {
  source = "../../../modules/aws/vpc-endpoints"

  name            = "${var.project}-${var.region_code}-shared"
  vpc_id          = var.shared_services_vpc.vpc_id
  subnet_ids      = var.shared_services_vpc.endpoint_subnet_ids
  route_table_ids = var.shared_services_vpc.route_table_ids
  allowed_cidrs   = var.dns_client_cidrs
  organization_id = var.organization_id
  enable_ipv6     = var.enable_ipv6
  tags            = local.tags
}
