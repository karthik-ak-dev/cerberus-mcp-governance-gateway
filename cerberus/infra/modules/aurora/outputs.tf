# Aurora Module Outputs

output "cluster_endpoint" {
  description = "Aurora cluster writer endpoint"
  value       = aws_rds_cluster.main.endpoint
}

output "cluster_reader_endpoint" {
  description = "Aurora cluster reader endpoint"
  value       = aws_rds_cluster.main.reader_endpoint
}

output "cluster_id" {
  description = "Aurora cluster identifier"
  value       = aws_rds_cluster.main.id
}

output "security_group_id" {
  description = "Aurora security group ID"
  value       = aws_security_group.aurora.id
}

output "database_name" {
  description = "Database name"
  value       = aws_rds_cluster.main.database_name
}

output "port" {
  description = "Database port"
  value       = aws_rds_cluster.main.port
}
