output "standards_subscription_arns" {
  description = "ARNs for enabled SecurityHub standards subscriptions."
  value       = [for s in aws_securityhub_standards_subscription.standards : s.arn]
}
