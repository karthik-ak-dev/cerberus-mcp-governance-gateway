# App Runner Module Outputs

output "service_url" {
  description = "App Runner service URL"
  value       = aws_apprunner_service.main.service_url
}

output "service_arn" {
  description = "App Runner service ARN"
  value       = aws_apprunner_service.main.arn
}

output "service_id" {
  description = "App Runner service ID"
  value       = aws_apprunner_service.main.service_id
}

output "security_group_id" {
  description = "App Runner VPC connector security group ID"
  value       = var.security_group_id
}

output "vpc_connector_arn" {
  description = "VPC connector ARN"
  value       = aws_apprunner_vpc_connector.main.arn
}
