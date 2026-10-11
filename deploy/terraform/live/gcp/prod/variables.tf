variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "golden"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)."
  type        = string
  default     = "prod"
}

variable "region" {
  description = "Cloud region."
  type        = string
  default     = "us-central1"
}

variable "project_id" {
  description = "GCP project ID that hosts the environment."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version of the managed cluster."
  type        = string
  default     = "1.30"
}

variable "node_count" {
  description = "Node count of the general node pool."
  type        = number
  default     = 3
}

variable "node_instance_type" {
  description = "Instance / VM / machine type of the general node pool."
  type        = string
  default     = "e2-standard-8"
}

variable "gpu_node_pool_enabled" {
  description = "Create an NVIDIA GPU node pool (taint nvidia.com/gpu=present:NoSchedule) for gpu-optimizer."
  type        = bool
  default     = false
}

variable "gpu_instance_type" {
  description = "Instance / VM / machine type of the GPU node pool."
  type        = string
  default     = "n1-standard-4"
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
