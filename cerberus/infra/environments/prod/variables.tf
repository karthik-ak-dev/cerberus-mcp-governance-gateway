# Production Environment Variables

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "cerberus_admin"
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "secret_key" {
  description = "Application secret key (generate with: openssl rand -hex 32)"
  type        = string
  sensitive   = true
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "cors_origins" {
  description = "CORS allowed origins (JSON array string)"
  type        = string
  default     = "[\"https://yourdomain.com\"]"
}