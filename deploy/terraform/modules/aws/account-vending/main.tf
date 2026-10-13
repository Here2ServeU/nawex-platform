# ------------------------------------------------------------------------------
# AWS ACCOUNT VENDING MODULE (Organizations)
# ------------------------------------------------------------------------------
# Creates member accounts from a map and places each in its OU, so new accounts
# land under the SCPs/RCPs of modules/aws/org-guardrails from their first
# minute. Output `account_groups` has exactly the shape live/aws/org expects for
# var.account_groups (access-model account group -> account IDs), closing the
# loop from "vend an account" to "personas can sign in to it":
#
#   account-vending ──account_groups──▶ live/aws/org (identity-center assignments)
#                   └──ou placement───▶ org-guardrails (scp_targets / rcp_targets)
#
# Run from the management account (only it can call CreateAccount).
#
# Managed alternative: AWS Control Tower Account Factory for Terraform (AFT) does
# the same job as a pipeline (account request repo -> Service Catalog -> Control
# Tower enrollment -> account customizations) and adds Control Tower guardrails
# and baseline enrollment. Use AFT when Control Tower owns the landing zone; use
# this module when the organization is managed directly with Organizations +
# Terraform (as here). Do not use both for the same account.
# ------------------------------------------------------------------------------

resource "aws_organizations_account" "this" {
  for_each = var.accounts

  name                       = each.key
  email                      = each.value.email
  parent_id                  = each.value.ou_id
  role_name                  = var.role_name
  iam_user_access_to_billing = var.iam_user_access_to_billing
  close_on_deletion          = false # removing an entry never closes a real account

  tags = merge(var.tags, each.value.tags, {
    "golden:account-group" = each.value.account_group
  })

  lifecycle {
    # role_name is only used by CreateAccount; AWS does not return it on read,
    # and changing it would force a (destructive) replacement.
    ignore_changes  = [role_name, iam_user_access_to_billing]
    prevent_destroy = true
  }
}
