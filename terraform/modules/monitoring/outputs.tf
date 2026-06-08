output "alert_sns_topic_arn" {
  description = "ARN of the SNS topic for pipeline alerts"
  value       = aws_sns_topic.alerts.arn
}

output "alert_sns_topic_name" {
  description = "Name of the SNS topic for pipeline alerts"
  value       = aws_sns_topic.alerts.name
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.pipeline.dashboard_name
}
