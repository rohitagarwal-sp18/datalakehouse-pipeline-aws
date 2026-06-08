variable "project" {
  description = "Project name used as resource prefix"
  type        = string
}

variable "env" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}

variable "raw_lifecycle_ia_days" {
  description = "Days until Bronze objects transition to Standard-IA"
  type        = number
  default     = 90
}

variable "raw_lifecycle_glacier_days" {
  description = "Days until Bronze objects transition to Glacier"
  type        = number
  default     = 365
}

variable "athena_results_expiry_days" {
  description = "Days until Athena query result objects are deleted"
  type        = number
  default     = 30
}
