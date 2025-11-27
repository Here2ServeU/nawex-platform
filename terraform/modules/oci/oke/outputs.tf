output "cluster_id" {
  value = oci_containerengine_cluster.k8s_cluster.id
}

output "kubernetes_version" {
  value = oci_containerengine_cluster.k8s_cluster.kubernetes_version
}

output "node_pool_ids" {
  value = [for np in oci_containerengine_node_pool.node_pools : np.id]
}
