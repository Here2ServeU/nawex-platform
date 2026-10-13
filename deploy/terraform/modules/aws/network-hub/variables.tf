variable "name" {
  description = "Base name for the hub resources, e.g. golden-use1-hub."
  type        = string
}

variable "amazon_side_asn" {
  description = "Private BGP ASN for the Transit Gateway (64512-65534 or 4200000000-4294967294). Unique per region/hub."
  type        = number
  default     = 64512
}

variable "auto_accept_shared_attachments" {
  description = "Auto-accept attachments from accounts the TGW is shared with. Off by default: segment placement happens here."
  type        = bool
  default     = false
}

variable "transit_gateway_cidr_blocks" {
  description = "Optional TGW CIDR blocks (IPv4 /24 or larger, IPv6 /64 or larger) for Connect (GRE) peers."
  type        = list(string)
  default     = []
}

variable "enable_ipv6" {
  description = "Dual-stack: IPv6 on hub-owned attachments, ::/0 default routes, DUALSTACK resolver endpoints."
  type        = bool
  default     = false
}

variable "ram_principals" {
  description = "RAM principals the TGW and resolver rules are shared with: the organization ARN or OU ARNs (arn:aws:organizations::<mgmt>:ou/o-xxx/ou-xxx)."
  type        = list(string)
  default     = []
}

variable "shared_services_vpc" {
  description = "Shared-services VPC in this account: TGW attachment subnets (one per AZ, /28) and Route 53 Resolver endpoint subnets (>= 2 AZs)."
  type = object({
    vpc_id              = string
    tgw_subnet_ids      = list(string)
    resolver_subnet_ids = list(string)
  })
}

variable "spoke_attachments" {
  description = "Accepted workload VPC attachments (created from the spoke accounts) -> segment. Keys are stable names, e.g. payments-prod."
  type = map(object({
    attachment_id = string
    segment       = string
  }))
  default = {}

  validation {
    condition     = alltrue([for a in values(var.spoke_attachments) : contains(["prod", "nonprod", "shared"], a.segment)])
    error_message = "spoke_attachments[*].segment must be prod, nonprod or shared."
  }
}

variable "segment_cidrs" {
  description = "Summary CIDRs per segment (from `golden network plan`). prod's route table blackholes nonprod's and vice versa."
  type        = map(list(string))
  default     = {}
}

variable "inspection_enabled" {
  description = "Attach an inspection VPC (AWS Network Firewall / GWLB appliances) in appliance mode and default-route prod/nonprod to it."
  type        = bool
  default     = false
}

variable "inspect_east_west" {
  description = "With inspection_enabled, also send spoke <-> shared traffic through the inspection VPC (centralized east-west inspection)."
  type        = bool
  default     = false
}

variable "inspection_vpc" {
  description = "Inspection VPC and its TGW attachment subnets. Required when inspection_enabled."
  type = object({
    vpc_id         = string
    tgw_subnet_ids = list(string)
  })
  default = null
}

variable "flow_log_s3_arn" {
  description = "S3 bucket ARN (log-archive account) for TGW flow logs. Null = CloudWatch Logs log group + delivery role in this account."
  type        = string
  default     = null
}

variable "flow_log_retention_days" {
  description = "Retention for the CloudWatch flow-log group (when flow_log_s3_arn is null)."
  type        = number
  default     = 365
}

variable "flow_log_kms_key_arn" {
  description = "Optional KMS key ARN for the CloudWatch flow-log group."
  type        = string
  default     = null
}

variable "permissions_boundary_arn" {
  description = "Permissions boundary for the flow-log delivery role (enforce-permission-boundary SCP / aws-iam.rego)."
  type        = string
  default     = null
}

variable "resolver_enabled" {
  description = "Create Route 53 Resolver inbound/outbound endpoints in the shared-services VPC (hybrid DNS)."
  type        = bool
  default     = true
}

variable "dns_client_cidrs" {
  description = "CIDRs allowed to query the resolver endpoints on 53/tcp+udp: the org supernet and on-prem."
  type        = list(string)
  default     = ["10.0.0.0/8"]
}

variable "onprem_dns_cidrs" {
  description = "On-prem DNS server CIDRs the outbound endpoint may forward to."
  type        = list(string)
  default     = []
}

variable "onprem_forward_domains" {
  description = "On-prem domain -> on-prem DNS server IPs. Becomes FORWARD resolver rules shared to the org via RAM."
  type        = map(list(string))
  default     = {}
}

variable "direct_connect_enabled" {
  description = "Create a Direct Connect gateway, associate it with the TGW and place the DX attachment in the shared table."
  type        = bool
  default     = false
}

variable "direct_connect_amazon_side_asn" {
  description = "Private ASN for the Direct Connect gateway (must differ from the TGW ASN and on-prem ASNs)."
  type        = number
  default     = 64513
}

variable "direct_connect_allowed_prefixes" {
  description = "Prefixes advertised to on-prem over the DX gateway association (AWS summaries, max 200 per association)."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
