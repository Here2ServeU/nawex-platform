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
  default     = 3
}

variable "node_instance_type" {
  description = "Instance / VM / machine type of the general node pool."
  type        = string
  default     = "m6i.xlarge"
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

variable "api_server_authorized_cidrs" {
  description = "CIDRs allowed to reach the Kubernetes API server (VPN / office egress). Empty = private-only API endpoint; deploy from inside the network."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.api_server_authorized_cidrs : can(cidrhost(c, 0)) && c != "0.0.0.0/0" && c != "::/0"])
    error_message = "api_server_authorized_cidrs must be valid CIDRs and must not contain 0.0.0.0/0 or ::/0."
  }
}
