# ------------------------------------------------------------------------------
# Golden platform — GCP organization governance & identity
#
# Applied once per organization, separately from the per-environment landing
# zones in live/gcp/{dev,staging,prod} (the GCP twin of live/aws/org):
#
#   org_governance   folder hierarchy, organization policy constraints, persona
#                    IAM from security/identity/gcp-access-model.yaml (folder /
#                    org bindings, PAM entitlements) and the org IAM deny policy
#
# Lint the model first: `golden iam multicloud` (golden.identity.multicloud).
# ------------------------------------------------------------------------------

locals {
  access_model = yamldecode(file("${path.module}/../../../../../security/identity/gcp-access-model.yaml"))
}

module "org_governance" {
  source = "../../../modules/gcp/org-governance"

  org_id        = var.org_id
  customer_id   = var.customer_id
  folder_prefix = var.folder_prefix

  allowed_locations    = var.allowed_locations
  org_policies_enabled = var.org_policies_enabled
  dry_run_constraints  = var.dry_run_constraints

  identity_enabled          = var.identity_enabled
  access_model              = local.access_model
  domain                    = var.domain
  verify_groups             = var.verify_groups
  pam_approvers             = var.pam_approvers
  deny_policy_enabled       = var.deny_policy_enabled
  deny_exception_principals = var.deny_exception_principals
}
