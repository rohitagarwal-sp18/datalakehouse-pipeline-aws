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

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_subnet" "first" {
  id = tolist(data.aws_subnets.default.ids)[0]
}

# ─── RDS SECURITY GROUP ───────────────────────────────────────────────────────

resource "aws_security_group" "rds" {
  name        = "${local.prefix}-rds-sg"
  description = "Controls access to the RDS PostgreSQL instance"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "PostgreSQL from Glue"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.glue.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${local.prefix}-rds-sg" })
}

# ─── GLUE SECURITY GROUP ──────────────────────────────────────────────────────

resource "aws_security_group" "glue" {
  name        = "${local.prefix}-glue-sg"
  description = "Security group for Glue JDBC connections — self-referencing rule required by Glue"
  vpc_id      = data.aws_vpc.default.id

  # Glue requires a self-referencing inbound rule to allow DPU-to-DPU communication
  ingress {
    description = "Glue self-referencing rule (required)"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, { Name = "${local.prefix}-glue-sg" })
}
