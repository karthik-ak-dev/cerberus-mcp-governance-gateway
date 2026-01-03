# Valkey Module Outputs

output "endpoint" {
  description = "Valkey primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "port" {
  description = "Valkey port"
  value       = 6379
}

output "security_group_id" {
  description = "Valkey security group ID"
  value       = aws_security_group.valkey.id
}

output "replication_group_id" {
  description = "Valkey replication group ID"
  value       = aws_elasticache_replication_group.main.replication_group_id
}
