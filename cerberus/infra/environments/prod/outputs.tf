# Production Environment Outputs

output "app_url" {
  description = "Application URL"
  value       = "https://${module.apprunner.service_url}"
}

output "ecr_repository_url" {
  description = "ECR repository URL for pushing images"
  value       = module.ecr.repository_url
}

output "aurora_endpoint" {
  description = "Aurora cluster endpoint"
  value       = module.aurora.cluster_endpoint
}

output "valkey_endpoint" {
  description = "Valkey endpoint"
  value       = module.valkey.endpoint
}

output "apprunner_service_arn" {
  description = "App Runner service ARN (for deployments)"
  value       = module.apprunner.service_arn
}
