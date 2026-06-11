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
