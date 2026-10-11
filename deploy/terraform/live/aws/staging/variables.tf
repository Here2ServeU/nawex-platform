variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "golden"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)."
  type        = string
  default     = "staging"
}

variable "region" {
  description = "Cloud region."
  type        = string
  default     = "us-east-1"
}

variable "kubernetes_version" {
  description = "Kubernetes version of the managed cluster."
  type        = string
  default     = "1.31"
}

variable "node_count" {
  description = "Node count of the general node pool."
  type        = number
  default     = 2
}

variable "node_instance_type" {
  description = "Instance / VM / machine type of the general node pool."
  type        = string
  default     = "m6i.large"
}

variable "gpu_node_pool_enabled" {
  description = "Create an NVIDIA GPU node pool (taint nvidia.com/gpu=present:NoSchedule) for gpu-optimizer."
  type        = bool
  default     = false
}

variable "gpu_instance_type" {
  description = "Instance / VM / machine type of the GPU node pool."
  type        = string
  default     = "g5.xlarge"
}

variable "gpu_node_count" {
  description = "Node count of the GPU node pool."
  type        = number
  default     = 1
}

variable "tags" {
  description = "Extra tags (AWS/Azure) or labels (GCP) applied to every resource."
  type        = map(string)
  default     = {}
}
