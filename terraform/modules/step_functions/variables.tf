variable "project" {
  description = "Project name used as resource prefix"
  type        = string
}

variable "env" {
  description = "Deployment environment (dev, prod)"
  type        = string
}

variable "step_functions_role_arn" {
  description = "IAM role ARN for the Step Functions state machine"
  type        = string
}

variable "state_machine_definition" {
  description = "ASL JSON definition of the pipeline state machine"
  type        = string
}

variable "log_level" {
  description = "Step Functions execution log level (OFF, ERROR, FATAL, ALL)"
  type        = string
  default     = "ERROR"
}

variable "tags" {
  description = "Additional resource tags"
  type        = map(string)
  default     = {}
}
