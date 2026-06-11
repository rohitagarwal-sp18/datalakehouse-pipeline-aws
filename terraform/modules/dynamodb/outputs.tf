output "watermarks_table_name" {
  description = "Name of the DynamoDB watermarks table"
  value       = aws_dynamodb_table.watermarks.name
}

output "watermarks_table_arn" {
  description = "ARN of the DynamoDB watermarks table"
  value       = aws_dynamodb_table.watermarks.arn
}
