variable "project_id" {}
variable "region" {}
variable "cluster_name" {}
variable "network" {}
variable "subnetwork" {}

variable "zones" {
  description = "List of zones. If 1 zone provided, creates Zonal cluster (Cheaper)."
  type        = list(string)
}

variable "ip_range_pods" {
  description = "The secondary range name for pods"
  type        = string
}

variable "ip_range_services" {
  description = "The secondary range name for services"
  type        = string
}

variable "node_pools" {
  description = "List of maps containing node pool configurations"
  type        = list(map(any))
}

variable "node_service_account" {
  description = "Email of the SA to run nodes as (Least Privilege)"
  type        = string
  default     = "" # If empty, GKE creates a default one (not recommended for Principal level)
}

variable "labels" {
  type = map(string)
}
