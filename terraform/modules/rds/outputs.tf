output "endpoint" {
  description = "RDS instance endpoint hostname"
  value       = aws_db_instance.app.address
}

output "port" {
  description = "RDS instance port"
  value       = aws_db_instance.app.port
}

output "db_name" {
  description = "Database name"
  value       = aws_db_instance.app.db_name
}

output "instance_id" {
  description = "RDS instance identifier"
  value       = aws_db_instance.app.identifier
}

output "secret_arn" {
  description = "ARN of the Secrets Manager secret containing DB credentials"
  value       = aws_secretsmanager_secret.rds.arn
}

output "availability_zone" {
  description = "Availability zone of the RDS instance"
  value       = aws_db_instance.app.availability_zone
}
