output "raw_bucket_id" {
  description = "Name of the raw (Bronze) S3 bucket"
  value       = aws_s3_bucket.raw.id
}

output "raw_bucket_arn" {
  description = "ARN of the raw (Bronze) S3 bucket"
  value       = aws_s3_bucket.raw.arn
}

output "processed_bucket_id" {
  description = "Name of the processed (Silver + Gold) S3 bucket"
  value       = aws_s3_bucket.processed.id
}

output "processed_bucket_arn" {
  description = "ARN of the processed (Silver + Gold) S3 bucket"
  value       = aws_s3_bucket.processed.arn
}

output "athena_results_bucket_id" {
  description = "Name of the Athena query results S3 bucket"
  value       = aws_s3_bucket.athena_results.id
}

output "athena_results_bucket_arn" {
  description = "ARN of the Athena query results S3 bucket"
  value       = aws_s3_bucket.athena_results.arn
}

output "glue_scripts_bucket_id" {
  description = "Name of the Glue scripts S3 bucket"
  value       = aws_s3_bucket.glue_scripts.id
}

output "glue_scripts_bucket_arn" {
  description = "ARN of the Glue scripts S3 bucket"
  value       = aws_s3_bucket.glue_scripts.arn
}
