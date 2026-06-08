output "bronze_database_name" {
  description = "Glue Catalog database name for the Bronze layer"
  value       = aws_glue_catalog_database.bronze.name
}

output "silver_database_name" {
  description = "Glue Catalog database name for the Silver layer"
  value       = aws_glue_catalog_database.silver.name
}

output "gold_database_name" {
  description = "Glue Catalog database name for the Gold layer"
  value       = aws_glue_catalog_database.gold.name
}

output "jdbc_connection_name" {
  description = "Name of the JDBC connection to RDS (empty if not created)"
  value       = var.create_jdbc_connection ? aws_glue_connection.rds[0].name : ""
}

output "bronze_crawler_name" {
  description = "Name of the Bronze layer Glue crawler"
  value       = var.create_crawlers ? aws_glue_crawler.bronze[0].name : ""
}

output "silver_crawler_name" {
  description = "Name of the Silver layer Glue crawler"
  value       = var.create_crawlers ? aws_glue_crawler.silver[0].name : ""
}

output "gold_crawler_name" {
  description = "Name of the Gold layer Glue crawler"
  value       = var.create_crawlers ? aws_glue_crawler.gold[0].name : ""
}

output "extraction_job_names" {
  description = "Names of extraction Glue jobs"
  value       = { for k, v in aws_glue_job.extraction : k => v.name }
}

output "etl_job_names" {
  description = "Names of ETL Glue jobs"
  value       = { for k, v in aws_glue_job.etl : k => v.name }
}
