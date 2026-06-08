variable "project" {
  description = "Project name used as resource prefix"
  type        = string
}

variable "env" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "raw_bucket_arn" {
  description = "ARN of the raw (Bronze) S3 bucket"
  type        = string
}

variable "processed_bucket_arn" {
  description = "ARN of the processed (Silver + Gold) S3 bucket"
  type        = string
}

variable "glue_scripts_bucket_arn" {
  description = "ARN of the Glue scripts S3 bucket"
  type        = string
}

variable "athena_results_bucket_arn" {
  description = "ARN of the Athena results S3 bucket"
  type        = string
}

variable "watermarks_table_arn" {
  description = "ARN of the DynamoDB watermarks table"
  type        = string
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
