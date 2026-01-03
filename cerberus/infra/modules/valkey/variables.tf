# Valkey Module Variables

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
  description = "List of subnet IDs for Valkey"
  type        = list(string)
}

variable "allowed_security_groups" {
  description = "Security groups allowed to connect to Valkey"
  type        = list(string)
  default     = []
}

variable "node_type" {
  description = "ElastiCache node type (e.g., cache.t4g.micro for staging, cache.t4g.small for prod)"
  type        = string
  default     = "cache.t4g.micro"
}
