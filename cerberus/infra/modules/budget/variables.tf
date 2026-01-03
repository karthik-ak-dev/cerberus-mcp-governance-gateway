# Budget Module Variables

variable "prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment name (stage, prod)"
  type        = string
}

variable "budget_amount" {
  description = "Monthly budget limit in USD"
  type        = string
}

variable "alert_emails" {
  description = "List of email addresses for budget alerts"
  type        = list(string)
  default     = []
}
