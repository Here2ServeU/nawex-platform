# ------------------------------------------------------------------------------
# AWS IAM IDENTITY CENTER MODULE
# ------------------------------------------------------------------------------
# Turns security/identity/access-model.yaml into Identity Center objects:
#
#   persona            -> aws_ssoadmin_permission_set (+ managed, customer-managed
#                         and inline policies, + permission boundary)
#   assignment.group   -> existing Identity Store group, SCIM-provisioned from
#                         Active Directory by PingFederate (looked up, never created
#                         here, so AD stays the source of truth for membership)
#   account_groups     -> account IDs from var.account_groups
#
# Run from the Identity Center delegated administrator (or management) account.
# ------------------------------------------------------------------------------

data "aws_partition" "current" {}

data "aws_ssoadmin_instances" "this" {}

locals {
  partition         = data.aws_partition.current.partition
  instance_arn      = tolist(data.aws_ssoadmin_instances.this.arns)[0]
  identity_store_id = tolist(data.aws_ssoadmin_instances.this.identity_store_ids)[0]

  boundary_name = var.access_model.permission_boundary
  boundary_arn  = "arn:${local.partition}:iam::*:policy/${local.boundary_name}"

  personas = { for p in var.access_model.personas : p.permission_set => p }

  # Lets a persona create and manage roles for its workloads, but only with the
  # boundary attached; the enforce-permission-boundary SCP backs this up.
  delegated_iam_statements = [
    {
      Sid    = "DelegatedRoleManagementWithBoundary"
      Effect = "Allow"
      Action = [
        "iam:CreateRole",
        "iam:PutRolePermissionsBoundary",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
      ]
      Resource = "*"
      Condition = {
        ArnLike = { "iam:PermissionsBoundary" = local.boundary_arn }
      }
    },
    {
      Sid    = "DelegatedRoleLifecycle"
      Effect = "Allow"
      Action = [
        "iam:DeleteRole",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:UpdateRole",
        "iam:UpdateAssumeRolePolicy",
        "iam:PassRole",
        "iam:CreatePolicy",
        "iam:CreatePolicyVersion",
        "iam:DeletePolicy",
        "iam:DeletePolicyVersion",
        "iam:CreateServiceLinkedRole",
      ]
      Resource = "*"
    },
  ]

  inline_policies = {
    for name, p in local.personas : name => jsonencode({
      Version = "2012-10-17"
      Statement = concat(
        try(p.inline_policy, []),
        [for s in local.delegated_iam_statements : s if try(p.delegated_iam, false)],
      )
    })
    if length(try(p.inline_policy, [])) > 0 || try(p.delegated_iam, false)
  }

  managed_attachments = merge([
    for name, p in local.personas : {
      for policy in try(p.aws_managed_policies, []) : "${name}|${policy}" => {
        permission_set = name
        arn            = "arn:${local.partition}:iam::aws:policy/${policy}"
      }
    }
  ]...)

  customer_managed_attachments = merge([
    for name, p in local.personas : {
      for policy in try(p.customer_managed_policies, []) : "${name}|${policy}" => {
        permission_set = name
        policy         = policy
      }
    }
  ]...)

  bounded = toset([for name, p in local.personas : name if try(p.permissions_boundary, false)])

  groups = toset(flatten([
    for p in local.personas : [for a in try(p.assignments, []) : a.group]
  ]))

  assignments = merge(flatten([
    for name, p in local.personas : [
      for a in try(p.assignments, []) : {
        for account in distinct(flatten([for g in a.account_groups : lookup(var.account_groups, g, [])])) :
        "${name}|${a.group}|${account}" => {
          permission_set = name
          group          = a.group
          account_id     = account
        }
      }
    ]
  ])...)
}

resource "aws_ssoadmin_permission_set" "this" {
  for_each = local.personas

  name             = each.key
  description      = substr(each.value.description, 0, 700)
  instance_arn     = local.instance_arn
  session_duration = try(each.value.session_duration, "PT8H")
  relay_state      = try(each.value.relay_state, null)

  tags = merge(var.tags, {
    "golden:persona"    = each.value.name
    "golden:privileged" = tostring(try(each.value.privileged, false))
  })
}

resource "aws_ssoadmin_managed_policy_attachment" "this" {
  for_each = local.managed_attachments

  instance_arn       = local.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.this[each.value.permission_set].arn
  managed_policy_arn = each.value.arn
}

resource "aws_ssoadmin_customer_managed_policy_attachment" "this" {
  for_each = local.customer_managed_attachments

  instance_arn       = local.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.this[each.value.permission_set].arn
  customer_managed_policy_reference {
    name = each.value.policy
    path = "/"
  }
}

resource "aws_ssoadmin_permission_set_inline_policy" "this" {
  for_each = local.inline_policies

  instance_arn       = local.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.this[each.key].arn
  inline_policy      = each.value
}

# The boundary policy must exist in every target account (modules/aws/permission-boundary).
resource "aws_ssoadmin_permissions_boundary_attachment" "this" {
  for_each = local.bounded

  instance_arn       = local.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.this[each.key].arn
  permissions_boundary {
    customer_managed_policy_reference {
      name = local.boundary_name
      path = "/"
    }
  }
}

# Groups come from Active Directory via SCIM; a missing group fails the plan
# instead of silently creating an empty, unmanaged group.
data "aws_identitystore_group" "this" {
  for_each = local.groups

  identity_store_id = local.identity_store_id
  alternate_identifier {
    unique_attribute {
      attribute_path  = "DisplayName"
      attribute_value = each.value
    }
  }
}

resource "aws_ssoadmin_account_assignment" "this" {
  for_each = local.assignments

  instance_arn       = local.instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.this[each.value.permission_set].arn
  principal_type     = "GROUP"
  principal_id       = data.aws_identitystore_group.this[each.value.group].group_id
  target_type        = "AWS_ACCOUNT"
  target_id          = each.value.account_id

  depends_on = [
    aws_ssoadmin_managed_policy_attachment.this,
    aws_ssoadmin_customer_managed_policy_attachment.this,
    aws_ssoadmin_permission_set_inline_policy.this,
    aws_ssoadmin_permissions_boundary_attachment.this,
  ]
}
