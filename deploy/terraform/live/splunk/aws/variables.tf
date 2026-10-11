variable "region" { type = string }
variable "name" { type = string }
variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "ami" { type = string }
variable "instance_type" {
  type    = string
  default = "t3.large"
}
variable "key_name" { type = string }
variable "admin_password" {
  type      = string
  sensitive = true
}
variable "hec_token" {
  type      = string
  sensitive = true
}
variable "allowed_cidr" {
  description = "CIDR allowed to reach Splunk Web/HEC (VPC or VPN range; 0.0.0.0/0 is rejected)."
  type        = string
}

variable "egress_cidr_blocks" {
  description = "Allowed outbound HTTP/HTTPS destinations (NAT/proxy ranges). Empty = no egress."
  type        = list(string)
  default     = []
}
