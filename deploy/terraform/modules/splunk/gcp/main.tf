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
    # No external IP by default; reach it through IAP / VPN / an internal LB.
    dynamic "access_config" {
      for_each = var.assign_public_ip ? [1] : []
      content {}
    }
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    block-project-ssh-keys = "true"
    enable-oslogin         = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    admin_password = var.admin_password
    hec_token      = var.hec_token
  })

  tags = ["splunk-enterprise"]
}
