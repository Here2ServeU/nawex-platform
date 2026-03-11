terraform {
  required_version = ">= 1.3.0"
}

provider "google" {
  project = var.project
  region  = var.region
}

module "splunk" {
  source = "../../../modules/splunk/gcp"

  name           = var.name
  zone           = var.zone
  network        = var.network
  subnetwork     = var.subnetwork
  machine_type   = var.machine_type
  image          = var.image
  admin_password = var.admin_password
  hec_token      = var.hec_token
}
