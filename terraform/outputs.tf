output "raw_bucket_name" {
  description = "Bronze layer S3 bucket name"
  value       = module.s3.raw_bucket_id
}

output "processed_bucket_name" {
  description = "Silver + Gold layer S3 bucket name"
  value       = module.s3.processed_bucket_id
}

output "athena_results_bucket_name" {
  description = "Athena query results S3 bucket name"
  value       = module.s3.athena_results_bucket_id
}

output "glue_scripts_bucket_name" {
  description = "Glue scripts S3 bucket name"
  value       = module.s3.glue_scripts_bucket_id
}

output "bronze_database_name" {
  description = "Glue Catalog database for Bronze layer"
  value       = module.glue.bronze_database_name
}

output "silver_database_name" {
  description = "Glue Catalog database for Silver layer"
  value       = module.glue.silver_database_name
}

output "gold_database_name" {
  description = "Glue Catalog database for Gold layer"
  value       = module.glue.gold_database_name
}

output "athena_workgroup_name" {
  description = "Athena workgroup name"
  value       = module.athena.workgroup_name
}

output "glue_extraction_role_arn" {
  description = "Glue extraction IAM role ARN"
  value       = module.iam.glue_extraction_role_arn
}

output "glue_etl_role_arn" {
  description = "Glue ETL IAM role ARN"
  value       = module.iam.glue_etl_role_arn
}

output "step_functions_role_arn" {
  description = "Step Functions IAM role ARN"
  value       = module.iam.step_functions_role_arn
}

output "watermarks_table_name" {
  description = "DynamoDB watermarks table name"
  value       = module.dynamodb.watermarks_table_name
}

output "rds_endpoint" {
  description = "RDS PostgreSQL instance endpoint"
  value       = module.rds.endpoint
}

output "rds_instance_id" {
  description = "RDS PostgreSQL instance identifier"
  value       = module.rds.instance_id
}

output "rds_secret_arn" {
  description = "Secrets Manager ARN for RDS credentials"
  value       = module.rds.secret_arn
}

output "state_machine_arn" {
  description = "Step Functions state machine ARN"
  value       = module.step_functions.state_machine_arn
}

output "state_machine_name" {
  description = "Step Functions state machine name"
  value       = module.step_functions.state_machine_name
}

output "alert_sns_topic_arn" {
  description = "SNS topic ARN for pipeline alerts"
  value       = module.monitoring.alert_sns_topic_arn
}
