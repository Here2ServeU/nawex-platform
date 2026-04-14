resource "aws_securityhub_account" "this" {
  count = var.enabled ? 1 : 0
}

resource "aws_securityhub_standards_subscription" "standards" {
  for_each      = var.enabled ? toset(var.standards_arns) : toset([])
  standards_arn = each.value
}
