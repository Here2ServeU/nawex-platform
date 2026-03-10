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
  description = "CIDR block allowed to access Splunk Web/HEC"
  type        = string
  default     = "0.0.0.0/0"
}
