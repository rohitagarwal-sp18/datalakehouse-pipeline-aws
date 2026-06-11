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

# ─── CATALOG DATABASES ───────────────────────────────────────────────────────

resource "aws_glue_catalog_database" "bronze" {
  name        = "${local.prefix}-bronze"
  description = "Raw data extracted from source systems — immutable CSV snapshots"
}

resource "aws_glue_catalog_database" "silver" {
  name        = "${local.prefix}-silver"
  description = "Cleaned, typed, deduplicated Parquet tables"
}

resource "aws_glue_catalog_database" "gold" {
  name        = "${local.prefix}-gold"
  description = "Analytics-ready aggregated tables for BI and Athena queries"
}

# ─── SECURITY CONFIGURATION ──────────────────────────────────────────────────

resource "aws_glue_security_configuration" "main" {
  name = "${local.prefix}-security-config"

  encryption_configuration {
    cloudwatch_encryption {
      cloudwatch_encryption_mode = "DISABLED"
    }
    job_bookmarks_encryption {
      job_bookmarks_encryption_mode = "DISABLED"
    }
    s3_encryption {
      s3_encryption_mode = "SSE-S3"
    }
  }
}

# ─── JDBC CONNECTION (Phase 3) ───────────────────────────────────────────────

resource "aws_glue_connection" "rds" {
  count = var.create_jdbc_connection ? 1 : 0

  name            = "${local.prefix}-rds-jdbc"
  connection_type = "JDBC"

  connection_properties = {
    JDBC_CONNECTION_URL = "jdbc:postgresql://${var.rds_endpoint}:5432/${var.rds_db_name}"
    USERNAME            = var.rds_username
    PASSWORD            = var.rds_password
  }

  physical_connection_requirements {
    availability_zone      = var.rds_availability_zone
    security_group_id_list = [var.glue_security_group_id]
    subnet_id              = var.rds_subnet_id
  }

  tags = local.tags
}

# ─── CRAWLERS (Phase 3) ──────────────────────────────────────────────────────

resource "aws_glue_crawler" "bronze" {
  count = var.create_crawlers ? 1 : 0

  name          = "${local.prefix}-bronze-crawler"
  role          = var.glue_etl_role_arn
  database_name = aws_glue_catalog_database.bronze.name
  schedule      = var.crawler_schedule != "" ? var.crawler_schedule : null

  s3_target {
    path = "s3://${var.raw_bucket_id}/bronze/"
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = local.tags
}

resource "aws_glue_crawler" "silver" {
  count = var.create_crawlers ? 1 : 0

  name          = "${local.prefix}-silver-crawler"
  role          = var.glue_etl_role_arn
  database_name = aws_glue_catalog_database.silver.name
  schedule      = var.crawler_schedule != "" ? var.crawler_schedule : null

  s3_target {
    path = "s3://${var.processed_bucket_id}/silver/"
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = local.tags
}

resource "aws_glue_crawler" "gold" {
  count = var.create_crawlers ? 1 : 0

  name          = "${local.prefix}-gold-crawler"
  role          = var.glue_etl_role_arn
  database_name = aws_glue_catalog_database.gold.name
  schedule      = var.crawler_schedule != "" ? var.crawler_schedule : null

  s3_target {
    path = "s3://${var.processed_bucket_id}/gold/"
  }

  schema_change_policy {
    update_behavior = "UPDATE_IN_DATABASE"
    delete_behavior = "DEPRECATE_IN_DATABASE"
  }

  tags = local.tags
}

# ─── EXTRACTION JOBS (Phase 3) ───────────────────────────────────────────────

resource "aws_glue_job" "extraction" {
  for_each = var.extraction_jobs

  name         = "${local.prefix}-${each.key}"
  role_arn     = var.glue_extraction_role_arn
  connections  = var.create_jdbc_connection ? [aws_glue_connection.rds[0].name] : []
  glue_version = "4.0"
  max_retries  = 1

  command {
    name            = "glueetl"
    script_location = "s3://${var.glue_scripts_bucket_id}/jobs/${each.value.script_name}"
    python_version  = "3"
  }

  default_arguments = merge(
    {
      "--job-language"                     = "python"
      "--enable-continuous-cloudwatch-log" = "true"
      "--enable-metrics"                   = "true"
      "--TempDir"                          = "s3://${var.glue_scripts_bucket_id}/temp/"
      "--RAW_BUCKET"                       = var.raw_bucket_id
      "--WATERMARKS_TABLE"                 = "${var.project}-${var.env}-watermarks"
      "--ENV"                              = var.env
      "--extra-jars"                       = "s3://${var.glue_scripts_bucket_id}/jars/postgresql-42.7.0.jar"
    },
    each.value.extra_args
  )

  number_of_workers = each.value.num_workers
  worker_type       = each.value.worker_type

  security_configuration = aws_glue_security_configuration.main.name

  tags = local.tags
}

# ─── ETL JOBS (Phase 4) ──────────────────────────────────────────────────────

resource "aws_glue_job" "etl" {
  for_each = var.etl_jobs

  name         = "${local.prefix}-${each.key}"
  role_arn     = var.glue_etl_role_arn
  glue_version = "4.0"
  max_retries  = 1

  command {
    name            = "glueetl"
    script_location = "s3://${var.glue_scripts_bucket_id}/jobs/${each.value.script_name}"
    python_version  = "3"
  }

  default_arguments = merge(
    {
      "--job-language"                     = "python"
      "--enable-continuous-cloudwatch-log" = "true"
      "--enable-metrics"                   = "true"
      "--enable-glue-datacatalog"          = "true"
      "--TempDir"                          = "s3://${var.glue_scripts_bucket_id}/temp/"
      "--RAW_BUCKET"                       = var.raw_bucket_id
      "--PROCESSED_BUCKET"                 = var.processed_bucket_id
      "--BRONZE_DB"                        = aws_glue_catalog_database.bronze.name
      "--SILVER_DB"                        = aws_glue_catalog_database.silver.name
      "--GOLD_DB"                          = aws_glue_catalog_database.gold.name
      "--ENV"                              = var.env
    },
    each.value.extra_args
  )

  number_of_workers = each.value.num_workers
  worker_type       = each.value.worker_type

  security_configuration = aws_glue_security_configuration.main.name

  tags = local.tags
}
