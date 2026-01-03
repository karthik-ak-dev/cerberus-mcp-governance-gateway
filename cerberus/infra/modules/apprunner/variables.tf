# App Runner Module Variables

variable "prefix" {
  description = "Resource name prefix (e.g., cerberus-stage)"
  type        = string
}

variable "environment" {
  description = "Environment name (stage/prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for VPC connector"
  type        = list(string)
}

variable "ecr_repository_url" {
  description = "ECR repository URL"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

# ------------------------------------------------------------------------------
# Instance Configuration
# ------------------------------------------------------------------------------

variable "cpu" {
  description = "CPU units (256, 512, 1024, 2048, 4096)"
  type        = string
  default     = "256"
}

variable "memory" {
  description = "Memory in MB (512, 1024, 2048, 3072, 4096, etc.)"
  type        = string
  default     = "512"
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 3
}

variable "max_concurrency" {
  description = "Max concurrent requests per instance"
  type        = number
  default     = 100
}

# ------------------------------------------------------------------------------
# Environment Variables (passed to container)
# ------------------------------------------------------------------------------

variable "environment_variables" {
  description = "Environment variables to pass to the container"
  type        = map(string)
  default     = {}
}

variable "security_group_id" {
  description = "Security group ID for VPC connector (passed from parent to break dependency cycles)"
  type        = string
}
