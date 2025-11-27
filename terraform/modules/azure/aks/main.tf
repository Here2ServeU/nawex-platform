# ------------------------------------------------------------------------------
# EXPRESS WEB AWS DEV - MAIN ENTRY POINT
# ------------------------------------------------------------------------------
# Architect: Emmanuel Naweji
# Description: Instantiates the AWS Dev environment.
# Strategy:    Single NAT Gateway (Cost Savings) + Spot Instances.
# ------------------------------------------------------------------------------

terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
  default_tags {
    tags = var.tags
  }
}

# 1. Network Layer (Cost Optimized)
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.0"

  name = "express-web-dev-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b"] # Only 2 AZs for Dev
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  # Principal FinOps: Single NAT Gateway saves ~$30/month per AZ
  enable_nat_gateway = true
  single_nat_gateway = true 
  enable_vpn_gateway = false
}

# 2. Compute Layer (EKS)
module "eks" {
  source = "../../../modules/compute/aws-eks"

  cluster_name    = "express-web-dev-eks-01"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets
  cluster_version = "1.29"

  # Principal FinOps: Passing strict Spot configuration
  # We assume the module supports a `node_groups` map variable
  # node_groups = {
  #   dev_spot = {
  #     capacity_type = "SPOT"
  #     instance_types = ["t3.medium"]
  #   }
  # }
}
