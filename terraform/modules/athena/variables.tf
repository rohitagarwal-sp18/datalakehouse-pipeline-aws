variable "project" {
  description = "Project name used as resource prefix"
  type        = string
}

variable "env" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "results_bucket_id" {
  description = "S3 bucket name for Athena query results"
  type        = string
}

variable "bytes_scanned_cutoff" {
  description = "Athena query cost control: max bytes scanned per query (default 1 GB)"
  type        = number
  default     = 1073741824
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
