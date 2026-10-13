output "account_ids" {
  description = "Account name -> 12-digit account ID."
  value       = { for k, a in aws_organizations_account.this : k => a.id }
}

output "account_arns" {
  description = "Account name -> ARN."
  value       = { for k, a in aws_organizations_account.this : k => a.arn }
}

output "account_groups" {
  description = "Access-model account group -> account IDs; pass to live/aws/org var.account_groups (merge with pre-existing accounts)."
  value = {
    for group in distinct([for a in values(var.accounts) : a.account_group]) : group => sort([
      for name, a in var.accounts : aws_organizations_account.this[name].id if a.account_group == group
    ])
  }
}
