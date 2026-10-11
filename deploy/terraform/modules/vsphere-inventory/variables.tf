variable "datacenter" {
  description = "vSphere datacenter name."
  type        = string
}

variable "vm_names" {
  description = "VM names in the migration wave."
  type        = list(string)
  default     = []
}

variable "datastores" {
  description = "Datastores to resolve (become StorageMap sources)."
  type        = list(string)
  default     = []
}

variable "networks" {
  description = "Port groups to resolve (become NetworkMap sources)."
  type        = list(string)
  default     = []
}
