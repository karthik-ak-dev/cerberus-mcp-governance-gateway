# ECR Module Variables

variable "repository_name" {
  description = "ECR repository name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "max_image_count" {
  description = "Maximum number of images to retain"
  type        = number
  default     = 10
}
