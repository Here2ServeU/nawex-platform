terraform {
  required_version = ">= 1.3.0"
}

provider "oci" {}

module "splunk" {
  source = "../../../modules/splunk/oci"

  compartment_ocid = var.compartment_ocid
  ad               = var.ad
  shape            = var.shape
  subnet_id        = var.subnet_id
  image_ocid       = var.image_ocid
  display_name     = var.display_name
  admin_password   = var.admin_password
  hec_token        = var.hec_token
}
