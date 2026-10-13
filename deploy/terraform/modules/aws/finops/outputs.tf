output "alerts_topic_arn" {
  description = "SNS topic that receives budget and anomaly notifications (subscribe ChatOps / PagerDuty here)."
  value       = aws_sns_topic.alerts.arn
}

output "kms_key_arn" {
  description = "Customer-managed KMS key encrypting the alert topic and the export bucket."
  value       = aws_kms_key.finops.arn
}

output "budget_names" {
  description = "Names of every budget created (account, linked accounts, teams)."
  value = concat(
    [aws_budgets_budget.account.name],
    [for b in aws_budgets_budget.linked_account : b.name],
    [for b in aws_budgets_budget.team : b.name],
  )
}

output "anomaly_monitor_arns" {
  description = "Cost Anomaly Detection monitor ARNs (SERVICE and, when teams are set, cost allocation tag)."
  value       = local.monitor_arns
}

output "export_bucket" {
  description = "S3 bucket holding the FOCUS export (null when enable_data_export = false)."
  value       = var.enable_data_export ? aws_s3_bucket.exports[0].id : null
}

output "export_arn" {
  description = "ARN of the FOCUS Data Export (null when enable_data_export = false)."
  value       = var.enable_data_export ? aws_bcmdataexports_export.focus[0].id : null
}

output "cost_allocation_tags" {
  description = "Tag keys activated as cost allocation tags."
  value       = sort([for t in aws_ce_cost_allocation_tag.required : t.tag_key])
}
