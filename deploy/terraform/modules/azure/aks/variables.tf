variable "cluster_name" {
  description = "AKS cluster name (also used as the DNS prefix)."
  type        = string
}

variable "resource_group_name" {
  description = "Resource group that holds the cluster."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "vnet_subnet_id" {
  description = "Subnet ID for the node pools (Azure CNI)."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version; null selects the AKS default."
  type        = string
  default     = null
}

variable "sku_tier" {
  description = "AKS control plane tier (Free or Standard)."
  type        = string
  default     = "Free"
}

variable "node_count" {
  type    = number
  default = 2
}

variable "node_min_count" {
  type    = number
  default = 1
}

variable "node_max_count" {
  type    = number
  default = 6
}

variable "node_instance_type" {
  description = "VM size of the system/general node pool."
  type        = string
  default     = "Standard_D4s_v5"
}

variable "enable_spot_instances" {
  description = "Add an autoscaling Spot user node pool."
  type        = bool
  default     = false
}

variable "user_max_count" {
  type    = number
  default = 5
}

variable "gpu_node_pool_enabled" {
  description = "Add an NVIDIA GPU node pool (tainted nvidia.com/gpu=present:NoSchedule)."
  type        = bool
  default     = false
}

variable "gpu_instance_type" {
  type    = string
  default = "Standard_NC4as_T4_v3"
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

variable "acr_id" {
  description = "ACR resource ID to grant AcrPull to the kubelet identity (null to skip)."
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
