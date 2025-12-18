# terraform/modules/redis/main.tf

resource "aws_elasticache_cluster" "redis_broker" {
  cluster_id           = var.cluster_id
  engine               = "redis"
  node_type            = var.node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  security_group_ids   = [var.security_group_id]
  subnet_group_name    = var.subnet_group_name
}

resource "aws_ssm_parameter" "redis_url" {
  name  = "/${var.env}/celery/redis_url"
  type  = "String"
  value = "redis://${aws_elasticache_cluster.redis_broker.cache_nodes[0].address}:6379/0"
}
