variable "cluster_endpoint" {
  description = "Kubernetes API server endpoint."
  type        = string
}

variable "cluster_ca" {
  description = "Base64 encoded cluster CA certificate."
  type        = string
}

variable "cluster_token" {
  description = "Bearer token for Kubernetes API."
  type        = string
  sensitive   = true
}
