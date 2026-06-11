variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile to use for authentication"
  type        = string
  default     = "learning"
}

variable "project" {
  description = "Project name prefix for all resources"
  type        = string
  default     = "datalakehouse"
}

variable "env" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "current_phase" {
  description = "Current build phase (for tagging)"
  type        = string
  default     = "1"
}

variable "alert_email" {
  description = "Email address to receive CloudWatch alarm notifications"
  type        = string
}

# ─── RDS (Phase 2) ───────────────────────────────────────────────────────────

variable "db_name" {
  description = "PostgreSQL database name for the e-commerce app"
  type        = string
  default     = "ecommerce"
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  sensitive   = true
  default     = "appuser"
}

variable "db_password" {
  description = "RDS master password — use a strong value in terraform.tfvars"
  type        = string
  sensitive   = true
}
