terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0.0"
    }
  }
}

resource "oci_core_instance" "splunk" {
  compartment_id      = var.compartment_ocid
  availability_domain = var.ad
  shape               = var.shape
  display_name        = var.display_name

  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true
  }

  source_details {
    source_type = "image"
    source_id   = var.image_ocid
  }

  metadata = {
    user_data = base64encode(templatefile("${path.module}/userdata.sh", {
      admin_password = var.admin_password
      hec_token      = var.hec_token
    }))
  }
}
