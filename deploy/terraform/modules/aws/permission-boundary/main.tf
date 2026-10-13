# ------------------------------------------------------------------------------
# AWS PERMISSION BOUNDARY MODULE
# ------------------------------------------------------------------------------
# The customer-managed boundary every role in a member account must carry
# (enforced by the enforce-permission-boundary SCP in modules/aws/org-guardrails
# and by security/policies/opa/aws-iam.rego at plan time).
#
# It is a delegation boundary, not a least-privilege policy: identity policies
# still grant the actual permissions. The boundary removes the paths that let a
# delegated principal escape governance:
#   * creating or editing roles without this boundary (privilege escalation)
#   * removing or rewriting the boundary itself
#   * long-lived IAM user credentials
#   * disabling security services or leaving the organization
# ------------------------------------------------------------------------------

data "aws_partition" "current" {}

locals {
  boundary_arn = "arn:${data.aws_partition.current.partition}:iam::*:policy${var.path}${var.name}"
}

data "aws_iam_policy_document" "boundary" {
  statement {
    sid       = "AllowWithinBoundary"
    effect    = "Allow"
    actions   = ["*"]
    resources = ["*"]
  }

  statement {
    sid    = "DenyPrincipalsWithoutBoundary"
    effect = "Deny"
    actions = [
      "iam:CreateRole",
      "iam:PutRolePermissionsBoundary",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
    ]
    resources = ["*"]
    condition {
      test     = "ArnNotLike"
      variable = "iam:PermissionsBoundary"
      values   = [local.boundary_arn]
    }
  }

  statement {
    sid    = "DenyBoundaryTampering"
    effect = "Deny"
    actions = [
      "iam:CreatePolicyVersion",
      "iam:DeletePolicy",
      "iam:DeletePolicyVersion",
      "iam:SetDefaultPolicyVersion",
    ]
    resources = [local.boundary_arn]
  }

  statement {
    sid    = "DenyBoundaryRemoval"
    effect = "Deny"
    actions = [
      "iam:DeleteRolePermissionsBoundary",
      "iam:DeleteUserPermissionsBoundary",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DenyLongLivedCredentials"
    effect = "Deny"
    actions = [
      "iam:CreateUser",
      "iam:CreateAccessKey",
      "iam:CreateLoginProfile",
      "iam:UpdateLoginProfile",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "DenySecurityAndOrgTampering"
    effect = "Deny"
    actions = [
      "organizations:*",
      "account:*",
      "cloudtrail:DeleteTrail",
      "cloudtrail:StopLogging",
      "cloudtrail:UpdateTrail",
      "config:DeleteConfigurationRecorder",
      "config:StopConfigurationRecorder",
      "guardduty:DeleteDetector",
      "securityhub:DisableSecurityHub",
      "access-analyzer:DeleteAnalyzer",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "boundary" {
  name        = var.name
  path        = var.path
  description = "Golden Platform permission boundary: blocks privilege escalation, boundary tampering and long-lived credentials."
  policy      = data.aws_iam_policy_document.boundary.json

  tags = merge(var.tags, { "golden:policy-type" = "permissions-boundary" })
}
