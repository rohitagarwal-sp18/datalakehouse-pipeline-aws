variable "project" {
  description = "Project name used as resource prefix"
  type        = string
}

variable "env" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "glue_extraction_role_arn" {
  description = "IAM role ARN for Glue extraction jobs"
  type        = string
}

variable "glue_etl_role_arn" {
  description = "IAM role ARN for Glue ETL jobs and crawlers"
  type        = string
}

variable "raw_bucket_id" {
  description = "Name of the raw (Bronze) S3 bucket"
  type        = string
}

variable "processed_bucket_id" {
  description = "Name of the processed (Silver + Gold) S3 bucket"
  type        = string
}

variable "glue_scripts_bucket_id" {
  description = "Name of the Glue scripts S3 bucket"
  type        = string
}

# ─── Phase 3: JDBC connection ────────────────────────────────────────────────

variable "create_jdbc_connection" {
  description = "Whether to create the JDBC connection to RDS (Phase 3+)"
  type        = bool
  default     = false
}

variable "rds_endpoint" {
  description = "RDS endpoint hostname (required if create_jdbc_connection = true)"
  type        = string
  default     = ""
}

variable "rds_db_name" {
  description = "RDS database name"
  type        = string
  default     = ""
}

variable "rds_username" {
  description = "RDS master username"
  type        = string
  default     = ""
  sensitive   = true
}

variable "rds_password" {
  description = "RDS master password"
  type        = string
  default     = ""
  sensitive   = true
}

variable "rds_availability_zone" {
  description = "AZ of the RDS instance (for Glue physical connection)"
  type        = string
  default     = ""
}

variable "glue_security_group_id" {
  description = "Security group ID for Glue JDBC connection"
  type        = string
  default     = ""
}

variable "rds_subnet_id" {
  description = "Subnet ID for Glue JDBC connection (must be same subnet as RDS)"
  type        = string
  default     = ""
}

# ─── Phase 3: Crawlers ───────────────────────────────────────────────────────

variable "create_crawlers" {
  description = "Whether to create Glue crawlers (Phase 3+)"
  type        = bool
  default     = false
}

variable "crawler_schedule" {
  description = "Cron expression for crawler schedule (empty = on-demand only)"
  type        = string
  default     = ""
}

# ─── Phase 3: Extraction jobs ────────────────────────────────────────────────

variable "extraction_jobs" {
  description = "Map of extraction Glue job configs (Phase 3+)"
  type = map(object({
    script_name = string
    num_workers = number
    worker_type = string
    extra_args  = map(string)
  }))
  default = {}
}

# ─── Phase 4: ETL jobs ───────────────────────────────────────────────────────

variable "etl_jobs" {
  description = "Map of ETL Glue job configs (Phase 4+)"
  type = map(object({
    script_name = string
    num_workers = number
    worker_type = string
    extra_args  = map(string)
  }))
  default = {}
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
