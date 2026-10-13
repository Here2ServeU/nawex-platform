# ------------------------------------------------------------------------------
# AWS ORGANIZATIONS GUARDRAILS MODULE (SCPs + RCPs)
# ------------------------------------------------------------------------------
# Preventive controls placed at the organization layer. Run from the management
# account (or the Organizations delegated administrator).
#
#   SCPs (limit what principals IN the org can do)
#     deny-root-and-iam-users       root user, IAM users/access keys, leaving the org
#     enforce-permission-boundary   every role must carry the workload boundary
#     protect-security-services     CloudTrail/Config/GuardDuty/Security Hub/SAML providers
#     region-allowlist              deny regional services outside allowed_regions
#   RCPs (limit what anyone can do TO resources in the org)
#     data-perimeter                org-only identities, confused-deputy, TLS-only
#
# Policies are JSON templates under policies/ so reviewers read real policy JSON;
# golden.identity and tests/test_identity.py render the same files to check
# validity and the 5,120-character Organizations size limit.
#
# Roll out per OU (sandbox → nonprod → prod) via scp_targets / rcp_targets; see
# ops/runbooks/identity/guardrail-rollout.md.
# ------------------------------------------------------------------------------

data "aws_partition" "current" {}

data "aws_organizations_organization" "current" {}

locals {
  template_vars = {
    partition            = data.aws_partition.current.partition
    org_id               = data.aws_organizations_organization.current.id
    boundary_policy_name = var.boundary_policy_name
    exempt_principals    = jsonencode(var.exempt_principal_arns)
    allowed_regions      = jsonencode(var.allowed_regions)
  }

  scps = {
    for f in fileset("${path.module}/policies/scp", "*.json.tftpl") :
    trimsuffix(f, ".json.tftpl") => "${path.module}/policies/scp/${f}"
    if contains(var.enabled_scps, trimsuffix(f, ".json.tftpl"))
  }
  rcps = {
    for f in fileset("${path.module}/policies/rcp", "*.json.tftpl") :
    trimsuffix(f, ".json.tftpl") => "${path.module}/policies/rcp/${f}"
    if contains(var.enabled_rcps, trimsuffix(f, ".json.tftpl"))
  }

  scp_attachments = merge([
    for policy, targets in var.scp_targets : {
      for t in targets : "${policy}|${t}" => { policy = policy, target = t }
    } if contains(keys(local.scps), policy)
  ]...)
  rcp_attachments = merge([
    for policy, targets in var.rcp_targets : {
      for t in targets : "${policy}|${t}" => { policy = policy, target = t }
    } if contains(keys(local.rcps), policy)
  ]...)
}

resource "aws_organizations_policy" "scp" {
  for_each = local.scps

  name        = "${var.name_prefix}-${each.key}"
  description = "Golden Platform guardrail (SCP): ${each.key}"
  type        = "SERVICE_CONTROL_POLICY"
  # Minified: Organizations counts whitespace against the 5,120-character limit.
  content = jsonencode(jsondecode(templatefile(each.value, local.template_vars)))

  tags = merge(var.tags, { "golden:control-layer" = "preventive-org" })
}

resource "aws_organizations_policy_attachment" "scp" {
  for_each = local.scp_attachments

  policy_id = aws_organizations_policy.scp[each.value.policy].id
  target_id = each.value.target
}

resource "aws_organizations_policy" "rcp" {
  for_each = local.rcps

  name        = "${var.name_prefix}-${each.key}"
  description = "Golden Platform guardrail (RCP): ${each.key}"
  type        = "RESOURCE_CONTROL_POLICY"
  content     = jsonencode(jsondecode(templatefile(each.value, local.template_vars)))

  tags = merge(var.tags, { "golden:control-layer" = "preventive-resource" })
}

resource "aws_organizations_policy_attachment" "rcp" {
  for_each = local.rcp_attachments

  policy_id = aws_organizations_policy.rcp[each.value.policy].id
  target_id = each.value.target
}
