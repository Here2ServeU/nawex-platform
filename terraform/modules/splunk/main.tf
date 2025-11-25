terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

# This module expects per-cloud submodules; here we only wire AWS as example.

locals {
  cloud = var.cloud
}

module "splunk_aws" {
  count  = local.cloud == "aws" ? 1 : 0
  source = "../../splunk/aws"

  project           = var.project
  subnet_id         = var.subnet_id
  security_group_id = var.security_group_id
  instance_type     = var.instance_type
  ami_id            = var.ami_id
  key_name          = var.key_name
  tags              = var.tags
}

output "splunk_ip" {
  value = try(module.splunk_aws[0].splunk_ip, null)
}

output "splunk_hec_url" {
  value = try("https://${module.splunk_aws[0].splunk_ip}:8088/services/collector", null)
}

output "splunk_hec_token" {
  value     = var.splunk_hec_token
  sensitive = true
}
