variable "project" {
  type    = string
  default = "golden"
}

variable "environment" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sku" {
  description = "Basic, Standard or Premium."
  type        = string
  default     = "Standard"
}

variable "tags" {
  type    = map(string)
  default = {}
}
