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

variable "permissions_boundary_arn" {
  description = "Permission boundary attached to every IAM role this module creates (modules/aws/permission-boundary). null = none."
  type        = string
  default     = null
}

# ------------------------------------------------------------------------------
# Karpenter
# ------------------------------------------------------------------------------
variable "karpenter_enabled" {
  description = "Install Karpenter (controller IRSA role, node role, SQS interruption queue, Helm release). Apply NodePools from deploy/k8s/platform-addons/karpenter/."
  type        = bool
  default     = false
}

variable "karpenter_chart_version" {
  description = "Karpenter Helm chart version (oci://public.ecr.aws/karpenter/karpenter)."
  type        = string
  default     = "1.1.1"
}

# ------------------------------------------------------------------------------
# Velero
# ------------------------------------------------------------------------------
variable "velero_enabled" {
  description = "Install Velero with a KMS-encrypted, versioned S3 bucket and an IRSA role (backup / DR)."
  type        = bool
  default     = false
}

variable "velero_bucket_name" {
  description = "Backup bucket name. null = \"<name>-velero-backups\" (S3 names are global; override if taken)."
  type        = string
  default     = null
}

variable "velero_namespace" {
  description = "Namespace for the Velero server."
  type        = string
  default     = "velero"
}

variable "velero_chart_version" {
  description = "Velero Helm chart version (vmware-tanzu/velero)."
  type        = string
  default     = "7.2.1"
}

variable "velero_aws_plugin_image" {
  description = "velero-plugin-for-aws image matching the Velero server version of the chart."
  type        = string
  default     = "velero/velero-plugin-for-aws:v1.10.0"
}

variable "velero_noncurrent_version_days" {
  description = "Days to keep noncurrent (overwritten / deleted) backup object versions."
  type        = number
  default     = 30
}

variable "velero_service_monitor_enabled" {
  description = "Render a ServiceMonitor for Velero metrics (requires the Prometheus Operator CRDs)."
  type        = bool
  default     = false
}
