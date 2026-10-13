# ------------------------------------------------------------------------------
# Golden platform — Azure tenant governance & identity
#
# Applied once per Entra tenant, separately from the per-environment landing
# zones in live/azure/{dev,staging,prod} (the Azure twin of live/aws/org):
#
#   governance   management-group hierarchy, subscription placement, Azure Policy
#                (locations, tags, no NIC public IPs, HTTPS storage, no classic,
#                Defender for Cloud) and the Entra ID persona model from
#                security/identity/azure-access-model.yaml (role assignments + PIM)
#
# Lint the model first: `golden iam multicloud` (golden.identity.multicloud).
# ------------------------------------------------------------------------------

locals {
  access_model = yamldecode(file("${path.module}/../../../../../security/identity/azure-access-model.yaml"))
}

module "governance" {
  source = "../../../modules/azure/governance"

  name_prefix                = var.project
  root_display_name          = var.root_display_name
  parent_management_group_id = var.parent_management_group_id
  subscription_placement     = var.subscription_placement

  location               = var.location
  allowed_locations      = var.allowed_locations
  required_tags          = var.required_tags
  enforce_policies       = var.enforce_policies
  policy_scope_overrides = var.policy_scope_overrides
  defender_enabled       = var.defender_enabled

  identity_enabled     = var.identity_enabled
  access_model         = local.access_model
  pim_eligibility_days = try(local.access_model.limits.max_eligibility_days, 365)
  pim_approver_group   = var.pim_approver_group
}
