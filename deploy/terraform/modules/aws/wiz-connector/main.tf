# ------------------------------------------------------------------------------
# WIZ CONNECTOR ROLE MODULE
# ------------------------------------------------------------------------------
# Read-only cross-account role Wiz assumes to scan an account (agentless posture,
# CIEM and entitlement analysis). Deploy into every member account (or via a
# StackSet) alongside modules/aws/permission-boundary.
#
# Trust is pinned to the Wiz-provided principal ARN and the tenant external ID,
# and the role carries the workload permission boundary like every other role.
# Wiz findings exported from the tenant feed `golden iam gaps`.
# ------------------------------------------------------------------------------

data "aws_partition" "current" {}

data "aws_iam_policy_document" "trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = [var.wiz_principal_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = [var.external_id]
    }
  }
}

resource "aws_iam_role" "wiz" {
  name                 = var.role_name
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  permissions_boundary = var.permissions_boundary_arn
  max_session_duration = 3600
  tags                 = merge(var.tags, { "golden:purpose" = "wiz-scanner" })
}

resource "aws_iam_role_policy_attachment" "read" {
  for_each = toset(["SecurityAudit", "job-function/ViewOnlyAccess"])

  role       = aws_iam_role.wiz.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.value}"
}

# Reads that SecurityAudit/ViewOnlyAccess miss but entitlement analysis needs.
data "aws_iam_policy_document" "extra_read" {
  statement {
    sid    = "EntitlementAndConfigReads"
    effect = "Allow"
    actions = [
      "iam:GenerateServiceLastAccessedDetails",
      "iam:GetServiceLastAccessedDetails",
      "iam:GetAccountAuthorizationDetails",
      "organizations:DescribePolicy",
      "organizations:ListPoliciesForTarget",
      "organizations:ListTargetsForPolicy",
      "sso:ListPermissionSetsProvisionedToAccount",
      "sso:DescribePermissionSet",
      "sso:GetInlinePolicyForPermissionSet",
      "sso:GetPermissionsBoundaryForPermissionSet",
      "identitystore:ListGroups",
      "identitystore:ListGroupMemberships",
      "ec2:GetEbsEncryptionByDefault",
      "kms:GetKeyRotationStatus",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "extra_read" {
  name   = "wiz-extra-read"
  role   = aws_iam_role.wiz.id
  policy = data.aws_iam_policy_document.extra_read.json
}
