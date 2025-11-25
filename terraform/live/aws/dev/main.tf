terraform {
  required_version = ">= 1.3.0"
  backend "s3" {
    bucket         = "emmanuel-tf-state-11202025"
    key            = "aws/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = "us-east-1"
}

module "backend" {
  source       = "../../modules/aws/backend"
  bucket_name  = "emmanuel-tf-state-11202025"
  lock_table   = "terraform-locks"
  aws_region   = "us-east-1"
  environment  = "dev"
}

module "registry" {
  source           = "../../modules/aws/registry"
  region           = "us-east-1"
  express_repo_name = "t2s-express-app"
  aiops_repo_name   = "aiops-api"
}

module "cluster" {
  source = "../../modules/aws/eks"
  region = "us-east-1"
  name   = "t2s-eks-dev"
}

# Splunk and GitOps wiring can be added using splunk and gitops modules
