# Aurora Module Variables

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
  description = "List of subnet IDs for Aurora"
  type        = list(string)
}

variable "allowed_security_groups" {
  description = "Security groups allowed to connect to Aurora"
  type        = list(string)
  default     = []
}

variable "engine_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "16.3"
}

variable "database_name" {
  description = "Default database name"
  type        = string
  default     = "cerberus"
}

variable "master_username" {
  description = "Master username"
  type        = string
  default     = "cerberus_admin"
}

variable "master_password" {
  description = "Master password"
  type        = string
  sensitive   = true
}

variable "min_capacity" {
  description = "Minimum ACUs (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "max_capacity" {
  description = "Maximum ACUs"
  type        = number
  default     = 4
}

variable "seconds_until_auto_pause" {
  description = "Seconds of inactivity before auto-pause (300-86400)"
  type        = number
  default     = 300 # 5 minutes
}

variable "backup_retention_days" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on deletion"
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
  default     = true
}
