variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "golden"
}

variable "region" {
  description = "Region of this hub (one root/state per region)."
  type        = string
  default     = "us-east-1"
}

variable "region_code" {
  description = "Short region code used in names, e.g. use1."
  type        = string
  default     = "use1"
}

variable "organization_id" {
  description = "AWS Organizations ID; VPC endpoint policies allow only its principals."
  type        = string
}

variable "ram_principals" {
  description = "Organization or OU ARNs the TGW and resolver rules are shared with."
  type        = list(string)
  default     = []
}

variable "tgw_asn" {
  description = "Transit Gateway private ASN (unique per regional hub)."
  type        = number
  default     = 64512
}

variable "enable_ipv6" {
  description = "Dual-stack hub (IPv6 on hub attachments, ::/0 routes, dual-stack endpoints)."
  type        = bool
  default     = false
}

variable "shared_services_vpc" {
  description = "Shared-services VPC: TGW, resolver and endpoint subnets plus the route tables for gateway endpoints."
  type = object({
    vpc_id              = string
    tgw_subnet_ids      = list(string)
    resolver_subnet_ids = list(string)
    endpoint_subnet_ids = list(string)
    route_table_ids     = list(string)
  })
}

variable "spoke_attachments" {
  description = "Accepted spoke VPC attachments -> segment (prod, nonprod, shared)."
  type = map(object({
    attachment_id = string
    segment       = string
  }))
  default = {}
}

variable "segment_cidrs" {
  description = "Segment -> summary CIDRs from `golden network plan`; used for prod/nonprod blackholes."
  type        = map(list(string))
  default     = {}
}

variable "inspection_vpc" {
  description = "Inspection VPC (Network Firewall / GWLB) and its TGW subnets; null disables inspection."
  type = object({
    vpc_id         = string
    tgw_subnet_ids = list(string)
  })
  default = null
}

variable "inspect_east_west" {
  description = "Also inspect spoke <-> shared traffic (requires inspection_vpc)."
  type        = bool
  default     = false
}

variable "flow_log_s3_arn" {
  description = "Log-archive bucket ARN for TGW flow logs (null = CloudWatch Logs in this account)."
  type        = string
  default     = null
}

variable "permissions_boundary_arn" {
  description = "Workload permissions boundary ARN for roles created here."
  type        = string
  default     = null
}

variable "dns_client_cidrs" {
  description = "CIDRs allowed to use the resolver endpoints and interface endpoints (org supernet + on-prem)."
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

variable "onprem_dns_cidrs" {
  description = "On-prem DNS server CIDRs."
  type        = list(string)
  default     = []
}

variable "onprem_forward_domains" {
  description = "On-prem domain -> DNS server IPs (FORWARD rules)."
  type        = map(list(string))
  default     = {}
}

variable "direct_connect_enabled" {
  description = "Create a Direct Connect gateway associated with the TGW."
  type        = bool
  default     = false
}

variable "direct_connect_allowed_prefixes" {
  description = "AWS summaries advertised to on-prem over Direct Connect."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Extra tags merged into every resource."
  type        = map(string)
  default     = {}
}
