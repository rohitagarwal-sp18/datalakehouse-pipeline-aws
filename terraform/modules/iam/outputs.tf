output "glue_extraction_role_arn" {
  description = "ARN of the Glue extraction IAM role"
  value       = aws_iam_role.glue_extraction.arn
}

output "glue_extraction_role_name" {
  description = "Name of the Glue extraction IAM role"
  value       = aws_iam_role.glue_extraction.name
}

output "glue_etl_role_arn" {
  description = "ARN of the Glue ETL IAM role"
  value       = aws_iam_role.glue_etl.arn
}

output "glue_etl_role_name" {
  description = "Name of the Glue ETL IAM role"
  value       = aws_iam_role.glue_etl.name
}

output "step_functions_role_arn" {
  description = "ARN of the Step Functions IAM role"
  value       = aws_iam_role.step_functions.arn
}

output "step_functions_role_name" {
  description = "Name of the Step Functions IAM role"
  value       = aws_iam_role.step_functions.name
}
