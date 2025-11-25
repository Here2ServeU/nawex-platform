terraform {
  required_version = ">= 1.3.0"
  backend "oci" {
    namespace = "your_namespace"
    bucket    = "emmanuel-tf-state-11202025"
    region    = "us-ashburn-1"
    key       = "oci/dev/terraform.tfstate"
  }
}

provider "oci" {
  region = var.region
}

module "registry" {
  source         = "../../modules/oci/registry"
  region         = var.region
  compartment_id = var.compartment_id
  repo_name      = "t2s-express-repo"
}

module "oke" {
  source           = "../../modules/oci/oke"
  region           = var.region
  compartment_id   = var.compartment_id
  name             = "t2s-oke-dev"
  vcn_id           = var.vcn_id
}
