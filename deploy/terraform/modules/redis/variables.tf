variable "env" {
  description = "Environment name (e.g., prod, dev)"
  type        = string
}

variable "cluster_id" {
  description = "Id to assign the new Redis cluster"
  type        = string
}

variable "node_type" {
  description = "The instance class used by the cluster nodes"
  type        = string
  default     = "cache.t3.micro"
}

variable "security_group_id" {
  description = "The ID of the security group to associate with the cluster"
  type        = string
}

variable "subnet_group_name" {
  description = "The name of the cache subnet group to use for the cluster"
  type        = string
}
