output "transit_gateway_id" {
  description = "Transit Gateway ID; spoke landing zones attach to it."
  value       = module.network_hub.transit_gateway_id
}

output "route_table_ids" {
  description = "Segment -> TGW route table ID."
  value       = module.network_hub.route_table_ids
}

output "segmentation" {
  description = "Segment -> associated route table and propagation targets."
  value       = module.network_hub.segmentation
}

output "resolver_inbound_ips" {
  description = "Point on-prem conditional forwarders for AWS private zones here."
  value       = module.network_hub.resolver_inbound_ips
}

output "resolver_rule_ids" {
  description = "On-prem domain -> resolver rule ID shared via RAM."
  value       = module.network_hub.resolver_rule_ids
}

output "interface_endpoint_ids" {
  description = "Service -> interface endpoint ID in the shared-services VPC."
  value       = module.shared_endpoints.interface_endpoint_ids
}

output "gateway_prefix_list_ids" {
  description = "S3 / DynamoDB prefix list IDs for security group egress rules."
  value       = module.shared_endpoints.gateway_prefix_list_ids
}
