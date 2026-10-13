# ------------------------------------------------------------------------------
# AWS VPC ENDPOINTS MODULE (PrivateLink + gateway endpoints, org data perimeter)
# ------------------------------------------------------------------------------
# Keeps AWS API traffic off the internet and inside the organization:
#
#   interface endpoints   ecr.api, ecr.dkr, sts, logs, ssm, ssmmessages,
#                         ec2messages, secretsmanager, kms (private DNS on), one
#                         ENI per subnet, security group = 443 from the VPC CIDRs
#   gateway endpoints     s3, dynamodb on the given route tables (free)
#
# Endpoint policies allow only principals in the organization
# (aws:PrincipalOrgID). This is the NETWORK leg of the data perimeter:
#
#   identity leg   SCPs   (org-guardrails/policies/scp)    who in the org can act
#   resource leg   RCP    (org-guardrails/policies/rcp/data-perimeter)  only org
#                         identities can touch org resources
#   network leg    THIS   from inside our VPCs, only org identities can use the
#                         endpoint: stolen credentials of a foreign account cannot
#                         be used to exfiltrate through our network path.
#
# Deploy into the shared-services VPC and share the private DNS through Route 53
# profiles / PHZ associations (centralized endpoints), or into each spoke VPC
# (simpler, more ENIs). See docs/networking/README.md#privatelink.
# ------------------------------------------------------------------------------

data "aws_region" "current" {}

data "aws_vpc_endpoint_service" "interface" {
  for_each = toset(var.interface_services)

  service      = each.value
  service_type = "Interface"
}

locals {
  org_policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Sid       = "AllowOrgPrincipalsOnly"
        Effect    = "Allow"
        Principal = "*"
        Action    = "*"
        Resource  = "*"
        Condition = { StringEquals = { "aws:PrincipalOrgID" = var.organization_id } }
      }],
      # AWS services acting on our behalf through the endpoint (e.g. ECR pulling layers).
      length(var.extra_allowed_principal_arns) == 0 ? [] : [{
        Sid       = "AllowListedPrincipals"
        Effect    = "Allow"
        Principal = { AWS = var.extra_allowed_principal_arns }
        Action    = "*"
        Resource  = "*"
      }],
    )
  })

  # ECR stores image layers in AWS-owned S3 buckets; the S3 gateway policy must allow
  # reads from them or image pulls fail. Layer downloads use pre-signed URLs issued by
  # ECR (an AWS-owned principal), so this one statement is scoped by resource, not org.
  s3_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowOrgPrincipalsOnly"
        Effect    = "Allow"
        Principal = "*"
        Action    = "*"
        Resource  = "*"
        Condition = { StringEquals = { "aws:PrincipalOrgID" = var.organization_id } }
      },
      {
        Sid       = "AllowEcrLayerBucket"
        Effect    = "Allow"
        Principal = "*"
        Action    = ["s3:GetObject"]
        Resource  = ["arn:aws:s3:::prod-${data.aws_region.current.name}-starport-layer-bucket/*"]
      },
    ]
  })
}

resource "aws_security_group" "endpoints" {
  name        = "${var.name}-vpc-endpoints"
  description = "Interface VPC endpoints: HTTPS from inside the VPC"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-vpc-endpoints" })
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  for_each = toset(var.allowed_cidrs)

  security_group_id = aws_security_group.endpoints.id
  description       = "HTTPS from ${each.value}"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = can(cidrnetmask(each.value)) ? each.value : null
  cidr_ipv6         = can(cidrnetmask(each.value)) ? null : each.value
}

resource "aws_vpc_endpoint" "interface" {
  for_each = data.aws_vpc_endpoint_service.interface

  vpc_id              = var.vpc_id
  service_name        = each.value.service_name
  vpc_endpoint_type   = "Interface"
  subnet_ids          = var.subnet_ids
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = var.private_dns_enabled
  ip_address_type     = var.enable_ipv6 ? "dualstack" : "ipv4"
  policy              = contains(var.services_without_policy, each.key) ? null : local.org_policy

  tags = merge(var.tags, { Name = "${var.name}-${each.key}" })
}

resource "aws_vpc_endpoint" "gateway" {
  for_each = toset(var.gateway_services)

  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.${each.value}"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids
  policy            = each.value == "s3" ? local.s3_policy : local.org_policy

  tags = merge(var.tags, { Name = "${var.name}-${each.value}" })
}
