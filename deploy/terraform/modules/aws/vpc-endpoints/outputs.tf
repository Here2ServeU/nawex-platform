output "interface_endpoint_ids" {
  description = "Service -> interface endpoint ID."
  value       = { for k, e in aws_vpc_endpoint.interface : k => e.id }
}

output "interface_endpoint_dns" {
  description = "Service -> endpoint-specific DNS names (useful when private DNS is disabled)."
  value       = { for k, e in aws_vpc_endpoint.interface : k => [for d in e.dns_entry : d.dns_name] }
}

output "gateway_endpoint_ids" {
  description = "Service -> gateway endpoint ID."
  value       = { for k, e in aws_vpc_endpoint.gateway : k => e.id }
}

output "gateway_prefix_list_ids" {
  description = "Service -> AWS-managed prefix list ID (use in security group egress rules)."
  value       = { for k, e in aws_vpc_endpoint.gateway : k => e.prefix_list_id }
}

output "security_group_id" {
  description = "Security group attached to the interface endpoints."
  value       = aws_security_group.endpoints.id
}
