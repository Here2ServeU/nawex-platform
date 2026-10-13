variable "name" {
  description = "Name prefix for the endpoints and their security group."
  type        = string
}

variable "vpc_id" {
  description = "VPC to create the endpoints in."
  type        = string
}

variable "subnet_ids" {
  description = "Subnets (one per AZ) for interface endpoint ENIs."
  type        = list(string)
}

variable "route_table_ids" {
  description = "Route tables that get the S3 / DynamoDB gateway endpoint routes."
  type        = list(string)
  default     = []
}

variable "allowed_cidrs" {
  description = "CIDRs allowed to reach the interface endpoints on 443: the VPC CIDR(s), plus spoke supernets when centralized."
  type        = list(string)
}

variable "organization_id" {
  description = "AWS Organizations ID (o-xxxxxxxxxx); endpoint policies allow only principals in it."
  type        = string

  validation {
    condition     = can(regex("^o-[a-z0-9]{10,32}$", var.organization_id))
    error_message = "organization_id must look like o-xxxxxxxxxx."
  }
}

variable "interface_services" {
  description = "Interface (PrivateLink) endpoint service short names."
  type        = list(string)
  default     = ["ecr.api", "ecr.dkr", "sts", "logs", "ssm", "ssmmessages", "ec2messages", "secretsmanager", "kms"]
}

variable "gateway_services" {
  description = "Gateway endpoint services (route-table based, no hourly charge)."
  type        = list(string)
  default     = ["s3", "dynamodb"]
}

variable "services_without_policy" {
  description = "Interface services that get the default (full-access) endpoint policy, for services where custom endpoint policies are not supported. Check the AWS PrivateLink docs for the current list before adding services."
  type        = list(string)
  default     = []
}

variable "extra_allowed_principal_arns" {
  description = "Principals outside the org that may use the endpoints (e.g. a vendor role). Keep empty unless reviewed."
  type        = list(string)
  default     = []
}

variable "private_dns_enabled" {
  description = "Resolve the public service names to the endpoint ENIs inside the VPC. Set false when a central PHZ is shared instead."
  type        = bool
  default     = true
}

variable "enable_ipv6" {
  description = "Create dual-stack interface endpoints (subnets must have IPv6 CIDRs)."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
