terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.0"
    }
  }
}

resource "google_compute_instance" "splunk" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = var.image
    }
  }

  network_interface {
    network    = var.network
    subnetwork = var.subnetwork
    access_config {}
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    admin_password = var.admin_password
    hec_token      = var.hec_token
  })

  tags = ["splunk-enterprise"]
}
