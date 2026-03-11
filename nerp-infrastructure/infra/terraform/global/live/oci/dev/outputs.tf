# ------------------------------------------------------------------------------ 
# WEB-APP OCI OUTPUTS
# ------------------------------------------------------------------------------ 
# Purpose: Operational hand-off data. 
# ------------------------------------------------------------------------------ 
output "cluster_id" {
description = "The OCID of the OKE Cluster"
value       = module.oke_cluster.cluster_id
}
output "vcn_id" {
description = "The OCID of the Virtual Cloud Network"
value       = module.vcn.vcn_id
}
# --- The "Principal" Touch ---
output "connect_command" {
description = "Run this to configure kubectl for OCI"
value       = "oci ce cluster create-kubeconfig --cluster-id ${module.oke_cluster.cluster_id} --file $HOME/.kube/config --region ${var.region} --token-version 2.0.0"
}
output "node_pool_shape" {
description = "Verifying the Flex Infrastructure configuration"
value       = "VM.Standard.E4.Flex (1 OCPU, 8GB RAM)"
}
