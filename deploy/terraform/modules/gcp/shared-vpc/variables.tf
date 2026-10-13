variable "host_project_id" {
  description = "Shared VPC host project ID."
  type        = string
}

variable "name" {
  description = "Network name, e.g. golden-prod-vpc."
  type        = string
}

variable "mtu" {
  description = "Network MTU (1460 default; 1500 or 8896 for jumbo frames)."
  type        = number
  default     = 1460
}

variable "subnets" {
  description = "Subnet name -> region, primary range and named secondary ranges (e.g. { pods = \"10.64.0.0/14\", services = \"10.68.0.0/20\" } for GKE)."
  type = map(object({
    region           = string
    ip_cidr_range    = string
    secondary_ranges = optional(map(string), {})
  }))
}

variable "enable_ipv6" {
  description = "Dual-stack subnets (internal IPv6 ULA) and an IPv6 deny-all ingress rule."
  type        = bool
  default     = false
}

variable "flow_log_sampling" {
  description = "VPC flow log sampling rate (0.0-1.0). 0.5 is a common cost/visibility balance."
  type        = number
  default     = 0.5
}

variable "router_asn" {
  description = "Private BGP ASN for the Cloud Routers (also used by Interconnect / HA VPN attachments)."
  type        = number
  default     = 64514
}

variable "iap_ssh_target_tags" {
  description = "Network tags that accept IAP SSH. Empty = every instance in the network."
  type        = list(string)
  default     = []
}

variable "psc_enabled" {
  description = "Create a Private Service Connect endpoint for Google APIs and a private googleapis.com zone."
  type        = bool
  default     = true
}

variable "psc_address" {
  description = "Internal IP for the PSC endpoint. Must be outside every subnet range."
  type        = string
  default     = "10.255.255.254"
}

variable "psc_endpoint_name" {
  description = "PSC forwarding rule name: 1-20 lowercase letters and digits, starting with a letter."
  type        = string
  default     = "googleapis"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{0,19}$", var.psc_endpoint_name))
    error_message = "psc_endpoint_name must be 1-20 lowercase letters/digits starting with a letter."
  }
}

variable "psc_bundle" {
  description = "Google APIs bundle: all-apis, or vpc-sc (only APIs supported by VPC Service Controls)."
  type        = string
  default     = "all-apis"

  validation {
    condition     = contains(["all-apis", "vpc-sc"], var.psc_bundle)
    error_message = "psc_bundle must be all-apis or vpc-sc."
  }
}

variable "service_project_ids" {
  description = "Service projects attached to this host project."
  type        = list(string)
  default     = []
}

variable "subnet_users" {
  description = "Subnet name -> members granted roles/compute.networkUser on it (e.g. serviceAccount:service-<num>@container-engine-robot.iam.gserviceaccount.com)."
  type        = map(list(string))
  default     = {}
}
