locals {
  prefix = "${var.project}-${var.env}"
  tags = merge(
    {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# ─── DB SUBNET GROUP ─────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "app" {
  name        = "${local.prefix}-db-subnet-group"
  subnet_ids  = var.subnet_ids
  description = "Subnet group for ${local.prefix} RDS instance"
  tags        = local.tags
}

# ─── PARAMETER GROUP ─────────────────────────────────────────────────────────

resource "aws_db_parameter_group" "app" {
  name        = "${local.prefix}-postgres15"
  family      = "postgres15"
  description = "Parameter group for ${local.prefix} PostgreSQL 15"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_duration"
    value = "1"
  }

  tags = local.tags
}

# ─── RDS INSTANCE ────────────────────────────────────────────────────────────

resource "aws_db_instance" "app" {
  identifier = "${local.prefix}-app-db"

  engine         = "postgres"
  engine_version = "15"
  instance_class = var.instance_class

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  allocated_storage     = var.allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true

  db_subnet_group_name   = aws_db_subnet_group.app.name
  vpc_security_group_ids = [var.rds_security_group_id]
  parameter_group_name   = aws_db_parameter_group.app.name

  multi_az               = var.multi_az
  publicly_accessible    = false
  deletion_protection    = var.deletion_protection
  skip_final_snapshot    = var.env == "prod" ? false : true
  final_snapshot_identifier = var.env == "prod" ? "${local.prefix}-final-snapshot" : null

  backup_retention_period = var.backup_retention_days
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_enhanced_monitoring.arn

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = local.tags
}

# ─── ENHANCED MONITORING ROLE ────────────────────────────────────────────────

data "aws_iam_policy_document" "rds_monitoring_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "rds_enhanced_monitoring" {
  name               = "${local.prefix}-rds-monitoring-role"
  assume_role_policy = data.aws_iam_policy_document.rds_monitoring_assume_role.json
  tags               = local.tags
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ─── SECRETS MANAGER ─────────────────────────────────────────────────────────

resource "aws_secretsmanager_secret" "rds" {
  name        = "${local.prefix}-rds-credentials"
  description = "RDS credentials for ${local.prefix} app database"
  tags        = local.tags
}

resource "aws_secretsmanager_secret_version" "rds" {
  secret_id = aws_secretsmanager_secret.rds.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = aws_db_instance.app.address
    port     = aws_db_instance.app.port
    dbname   = var.db_name
  })
}
