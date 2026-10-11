variable "name" {
  description = "Name prefix for the Splunk EC2 instance"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where Splunk will be deployed"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for the Splunk EC2 instance"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for Splunk"
  type        = string
  default     = "t3.large"
}

variable "ami" {
  description = "AMI ID for the the Splunk EC2 instance (Ubuntu/CentOS)"
  type        = string
}

variable "key_name" {
  description = "EC2 key pair name"
  type        = string
}

variable "admin_password" {
  description = "Splunk admin password"
  type        = string
  sensitive   = true
}

variable "hec_token" {
  description = "Splunk HEC token"
  type        = string
  sensitive   = true
}

variable "allowed_cidr" {
  description = "CIDR block allowed to access Splunk Web/HEC (e.g. the VPC or VPN range)."
  type        = string

  validation {
    condition     = can(cidrhost(var.allowed_cidr, 0)) && var.allowed_cidr != "0.0.0.0/0"
    error_message = "allowed_cidr must be a valid CIDR other than 0.0.0.0/0."
  }
}

variable "egress_cidr_blocks" {
  description = "Destinations allowed for outbound HTTP/HTTPS (NAT/proxy/VPC endpoint ranges). Empty = no egress."
  type        = list(string)
  default     = []
}

variable "associate_public_ip" {
  description = "Give the instance a public IP (not recommended; prefer a load balancer or VPN)."
  type        = bool
  default     = false
}

variable "root_volume_size" {
  type    = number
  default = 100
}
