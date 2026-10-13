# ------------------------------------------------------------------------------
# Golden platform — AWS organization identity & governance
#
# Applied once per organization from the management account (or the delegated
# administrator for Organizations + IAM Identity Center), separately from the
# per-environment landing zones in live/aws/{dev,staging,prod}:
#
#   org_guardrails   SCPs + RCPs attached per OU (preventive, org layer)
#   identity_center  persona permission sets + AD/SCIM group assignments
#                    from security/identity/access-model.yaml
#
# Every plan is gated by security/policies/opa/aws-iam.rego (`make iam-plan`).
# ------------------------------------------------------------------------------

locals {
  tags = merge({
    Project   = var.project
    Scope     = "organization"
    ManagedBy = "terraform"
  }, var.tags)

  access_model = yamldecode(file("${path.module}/../../../../../security/identity/access-model.yaml"))
}

module "org_guardrails" {
  source = "../../../modules/aws/org-guardrails"

  name_prefix           = var.project
  allowed_regions       = var.allowed_regions
  boundary_policy_name  = local.access_model.permission_boundary
  exempt_principal_arns = var.exempt_principal_arns
  scp_targets           = var.scp_targets
  rcp_targets           = var.rcp_targets
  tags                  = local.tags
}

module "identity_center" {
  source = "../../../modules/aws/identity-center"
  count  = var.identity_center_enabled ? 1 : 0

  access_model   = local.access_model
  account_groups = var.account_groups
  tags           = local.tags
}
