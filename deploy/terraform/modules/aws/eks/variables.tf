variable "name" {
  description = "Cluster / base resource name."
  type        = string
}

variable "region" {
  description = "AWS region."
  type        = string
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version."
  type        = string
  default     = "1.31"
}

variable "vpc_cidr" {
  description = "VPC CIDR (split into /20 public and private subnets)."
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "Number of availability zones to use."
  type        = number
  default     = 3
}

variable "single_nat_gateway" {
  description = "Use one shared NAT gateway (cheaper) instead of one per AZ."
  type        = bool
  default     = true
}

variable "node_count" {
  description = "Desired node count of the general node group."
  type        = number
  default     = 2
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
  description = "Instance type of the general node group."
  type        = string
  default     = "m6i.large"
}

variable "gpu_node_pool_enabled" {
  description = "Create an NVIDIA GPU node group (tainted nvidia.com/gpu=present:NoSchedule)."
  type        = bool
  default     = false
}

variable "gpu_instance_type" {
  type    = string
  default = "g5.xlarge"
}

variable "gpu_node_count" {
  type    = number
  default = 1
}

variable "enable_alb_controller" {
  description = "Install the AWS Load Balancer Controller (ingressClassName alb)."
  type        = bool
  default     = true
}

variable "workload_namespace" {
  description = "Namespace of the platform ServiceAccount trusted by the workload IAM role."
  type        = string
  default     = "golden"
}

variable "workload_service_account" {
  description = "Name of the platform ServiceAccount trusted by the workload IAM role."
  type        = string
  default     = "golden"
}

variable "workload_policy_arns" {
  description = "IAM policy ARNs attached to the workload role."
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}

variable "api_server_authorized_cidrs" {
  description = "CIDRs allowed to reach the Kubernetes API server's public endpoint (e.g. your VPN / office egress). Empty = private-only API endpoint."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for c in var.api_server_authorized_cidrs : can(cidrhost(c, 0)) && c != "0.0.0.0/0" && c != "::/0"])
    error_message = "api_server_authorized_cidrs must be valid CIDRs and must not contain 0.0.0.0/0 or ::/0."
  }
}
