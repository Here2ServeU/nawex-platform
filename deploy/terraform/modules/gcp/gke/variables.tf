variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "name" {
  description = "Cluster / base resource name."
  type        = string
}

variable "regional" {
  description = "Regional (HA control plane, nodes in 3 zones) vs zonal cluster."
  type        = bool
  default     = true
}

variable "zone_suffix" {
  description = "Zone suffix used for zonal clusters (e.g. \"a\")."
  type        = string
  default     = "a"
}

variable "kubernetes_version" {
  description = "Minimum master version; null lets the release channel decide."
  type        = string
  default     = null
}

variable "release_channel" {
  type    = string
  default = "REGULAR"
}

variable "nodes_cidr" {
  type    = string
  default = "10.10.0.0/20"
}

variable "pods_cidr" {
  type    = string
  default = "10.20.0.0/14"
}

variable "services_cidr" {
  type    = string
  default = "10.24.0.0/20"
}

variable "master_cidr" {
  type    = string
  default = "172.16.0.0/28"
}

variable "node_count" {
  description = "Initial nodes per zone in the general pool."
  type        = number
  default     = 1
}

variable "node_min_count" {
  type    = number
  default = 1
}

variable "node_max_count" {
  type    = number
  default = 4
}

variable "node_instance_type" {
  type    = string
  default = "e2-standard-4"
}

variable "gpu_node_pool_enabled" {
  description = "Create an NVIDIA GPU node pool (tainted nvidia.com/gpu=present:NoSchedule)."
  type        = bool
  default     = false
}

variable "gpu_instance_type" {
  type    = string
  default = "n1-standard-4"
}

variable "gpu_accelerator_type" {
  type    = string
  default = "nvidia-tesla-t4"
}

variable "gpu_node_count" {
  type    = number
  default = 1
}

variable "workload_namespace" {
  type    = string
  default = "golden"
}

variable "workload_service_account" {
  type    = string
  default = "golden"
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "labels" {
  type    = map(string)
  default = {}
}
