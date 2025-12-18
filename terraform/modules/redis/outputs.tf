output "redis_endpoint" {
  description = "The DNS name of the cache cluster"
  value       = aws_elasticache_cluster.redis_broker.cache_nodes[0].address
}

output "redis_url_ssm_path" {
  description = "The SSM parameter path containing the full Redis URL"
  value       = aws_ssm_parameter.redis_url.name
}

output "redis_port" {
  description = "The port number on which the cache nodes are accepting connections"
  value       = aws_elasticache_cluster.redis_broker.port
}
