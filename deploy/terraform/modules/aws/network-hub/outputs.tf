output "transit_gateway_id" {
  description = "Transit Gateway ID (spoke accounts attach to it after accepting the RAM share)."
  value       = aws_ec2_transit_gateway.this.id
}

output "transit_gateway_arn" {
  description = "Transit Gateway ARN."
  value       = aws_ec2_transit_gateway.this.arn
}

output "route_table_ids" {
  description = "Segment -> TGW route table ID (prod, nonprod, shared, inspection)."
  value       = { for k, rt in aws_ec2_transit_gateway_route_table.this : k => rt.id }
}

output "segmentation" {
  description = "Effective design: segment -> route table it is associated with and tables it propagates into."
  value = {
    for s, rts in local.propagate_to : s => {
      associated_with = local.associate_with[s]
      propagates_to   = rts
    }
  }
}

output "shared_services_attachment_id" {
  description = "TGW attachment ID of the shared-services VPC."
  value       = aws_ec2_transit_gateway_vpc_attachment.shared_services.id
}

output "inspection_attachment_id" {
  description = "TGW attachment ID of the inspection VPC (null when inspection is disabled)."
  value       = try(aws_ec2_transit_gateway_vpc_attachment.inspection[0].id, null)
}

output "ram_share_arn" {
  description = "RAM resource share ARN for the TGW."
  value       = aws_ram_resource_share.tgw.arn
}

output "resolver_inbound_ips" {
  description = "Inbound resolver IPs: configure on-prem conditional forwarders for AWS private zones to these."
  value       = try([for ip in aws_route53_resolver_endpoint.inbound[0].ip_address : ip.ip], [])
}

output "resolver_rule_ids" {
  description = "On-prem domain -> FORWARD resolver rule ID (associate in spoke VPCs)."
  value       = { for k, r in aws_route53_resolver_rule.forward : k => r.id }
}

output "direct_connect_gateway_id" {
  description = "Direct Connect gateway ID (null when disabled)."
  value       = try(aws_dx_gateway.this[0].id, null)
}

output "flow_log_id" {
  description = "TGW flow log ID."
  value       = aws_flow_log.tgw.id
}
