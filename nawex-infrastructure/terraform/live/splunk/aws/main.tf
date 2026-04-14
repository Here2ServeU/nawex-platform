terraform {
  required_version = ">= 1.3.0"
}

provider "aws" {
  region = var.region
}

module "splunk" {
  source = "../../../modules/splunk/aws"

  name           = var.name
  vpc_id         = var.vpc_id
  subnet_id      = var.subnet_id
  ami            = var.ami
  instance_type  = var.instance_type
  key_name       = var.key_name
  admin_password = var.admin_password
  hec_token      = var.hec_token
  allowed_cidr   = var.allowed_cidr
}
