terraform {
  required_version = ">= 1.3.0"

  backend "s3" {
    bucket         = "emmanuel-tf-state-09042025"
    key            = "eks/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.55" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.29" }
    helm = { source = "hashicorp/helm", version = "~> 2.13" }
  }
}
