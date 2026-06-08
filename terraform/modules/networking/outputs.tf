output "vpc_id" {
  description = "ID of the VPC"
  value       = data.aws_vpc.default.id
}

output "subnet_ids" {
  description = "List of subnet IDs in the VPC"
  value       = data.aws_subnets.default.ids
}

output "first_subnet_id" {
  description = "First subnet ID (used for RDS + Glue connection)"
  value       = tolist(data.aws_subnets.default.ids)[0]
}

output "first_subnet_az" {
  description = "Availability zone of the first subnet"
  value       = data.aws_subnet.first.availability_zone
}

output "rds_security_group_id" {
  description = "Security group ID for RDS PostgreSQL"
  value       = aws_security_group.rds.id
}

output "glue_security_group_id" {
  description = "Security group ID for Glue JDBC connections"
  value       = aws_security_group.glue.id
}
