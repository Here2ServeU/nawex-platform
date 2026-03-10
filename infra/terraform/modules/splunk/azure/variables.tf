variable "name" {
  description = "Name prefix for Splunk VM"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group" {
  description = "Resource group name"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for NIC"
  type        = string
}

variable "vm_size" {
  description = "VM size"
  type        = string
  default     = "Standard_D4s_v3"
}

variable "ssh_public_key" {
  description = "Path to SSH public key"
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
