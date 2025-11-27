variable "compartment_id" {}
variable "cluster_name" {}
variable "vcn_id" {}
variable "k8s_version" { default = "v1.29.1" }

variable "pod_subnet_ids" {
  description = "Subnets for worker nodes"
  type        = list(string)
}

variable "service_lb_subnet_ids" {
  description = "Subnets for Load Balancers"
  type        = list(string)
}

variable "node_pools" {
  description = "Map of node pool configurations (Flex shapes)"
  type = map(object({
    shape         = string
    ocpus         = number
    memory_in_gbs = number
    node_count    = number
  }))
}

# Map generic shapes to specific Image OCIDs (You would usually look this up dynamically)
variable "node_image_id_map" {
  type = map(string)
  default = {
    # Example Oracle Linux 8 image for E4 Flex
    "VM.Standard.E4.Flex" = "ocid1.image.oc1.iad.example..." 
  }
}

variable "tags" {
  type = map(string)
}
