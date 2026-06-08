output "state_machine_arn" {
  description = "ARN of the pipeline Step Functions state machine"
  value       = aws_sfn_state_machine.pipeline.arn
}

output "state_machine_name" {
  description = "Name of the pipeline Step Functions state machine"
  value       = aws_sfn_state_machine.pipeline.name
}

output "log_group_name" {
  description = "CloudWatch log group name for Step Functions executions"
  value       = aws_cloudwatch_log_group.sfn.name
}
