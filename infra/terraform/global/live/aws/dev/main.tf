# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Instantiates the Network and Compute layers for the Dev environment.
# Strategy:    Consumes versioned modules to ensure immutable infrastructure.
# ------------------------------------------------------------------------------

# 1. Network Layer (The Nervous System)
# We use the community standard module here to demonstrate we don't
# "reinvent the wheel" for standard components like VPCs.
module "vpc" {
  source          = "terraform-aws-modules/vpc/aws"
  version         = "5.1.0"
  name            = "web-app-dev-vpc"
  cidr            = "10.0.0.0/16"
  azs             = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  # Principal Choice: High Availability for Dev (Multi-NAT)
  enable_nat_gateway = true
  single_nat_gateway = false
  enable_vpn_gateway = false

  # Tagging for FinOps/Cost Allocation
  tags = merge(var.tags, { Layer = "Network" })
}

# 2. Compute Layer (The Body) - EKS Cluster
# This consumes OUR proprietary module from ../../../modules/compute/aws-eks
# This is where the specific "web-app" configuration lives (Spot instances, etc.)
module "eks_cluster" {
  source       = "../../../modules/compute/aws-eks"
  cluster_name = "web-app-dev-01"
  k8s_version  = "1.29"

  # Inject Network Dependencies
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Security & Compliance (SOC2)
  # In a real scenario, you'd pass a KMS Key ARN here
  # kms_key_arn = aws_kms_key.web_app_encryption.arn 
}

# 3. (Optional) Data Layer - RDS Database
# Uncomment to show you understand stateful persistence
# module "db" {
#   source = "../../../modules/data/aws-rds"
#   ...
# }

# 4. Redis
module "redis_celery" {
  source            = "../../modules/redis"
  env               = "dev"
  cluster_id        = "aiops-dev-redis"
  node_type         = "cache.t3.micro"
  security_group_id = module.vpc.internal_sg_id
  subnet_group_name = module.vpc.private_subnet_group
}

# 5. Security & Compliance (SecurityHub + Config)
# Enables AWS SecurityHub for finding centralization and AWS Config for resource tracking.
module "securityhub" {
  source  = "../../../modules/aws/securityhub"
  enabled = true
  standards_arns = [
    "arn:aws:securityhub:::standards/aws-foundational-security-best-practices/v/1.0.0"
  ]
}

module "config" {
  source        = "../../../modules/aws/config"
  name          = "aiops-dev-config"
  bucket_name   = "aiops-dev-config-logs-${data.aws_caller_identity.current.account_id}"
  create_bucket = true
  tags          = merge(var.tags, { Layer = "Security" })
}

data "aws_caller_identity" "current" {}
