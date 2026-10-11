# ------------------------------------------------------------------------------
# Golden platform landing zone - AWS / prod
# Generated layout: every live/{aws,azure,gcp}/{dev,staging,prod} directory
# exposes the same inputs (variables.tf) and outputs (outputs.tf).
# ------------------------------------------------------------------------------

locals {
  name = "${var.project}-${var.environment}"
  tags = merge({
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  }, var.tags)
}

module "registry" {
  source  = "../../../modules/aws/registry"
  project = var.project
  tags    = local.tags
}

module "eks" {
  source = "../../../modules/aws/eks"

  name               = local.name
  region             = var.region
  kubernetes_version = var.kubernetes_version
  single_nat_gateway = var.environment != "prod"

  node_count         = var.node_count
  node_instance_type = var.node_instance_type

  gpu_node_pool_enabled = var.gpu_node_pool_enabled
  gpu_instance_type     = var.gpu_instance_type
  gpu_node_count        = var.gpu_node_count

  workload_namespace       = "golden"
  workload_service_account = "golden"

  tags = local.tags

  api_server_authorized_cidrs = var.api_server_authorized_cidrs
}
