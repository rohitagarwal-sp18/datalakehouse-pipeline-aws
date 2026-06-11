variable "project" {
  description = "Project name used as resource prefix"
  type        = string
}

variable "env" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "alert_email" {
  description = "Email address to receive pipeline failure alerts"
  type        = string
}

variable "glue_job_names" {
  description = "List of Glue job names to monitor for failures"
  type        = list(string)
  default     = []
}

variable "state_machine_arn" {
  description = "ARN of the Step Functions state machine to monitor (empty = not yet created)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
