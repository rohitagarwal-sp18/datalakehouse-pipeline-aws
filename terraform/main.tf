module "s3" {
  source  = "./modules/s3"
  project = var.project
  env     = var.env
}

module "dynamodb" {
  source  = "./modules/dynamodb"
  project = var.project
  env     = var.env
}

module "iam" {
  source  = "./modules/iam"
  project = var.project
  env     = var.env

  raw_bucket_arn            = module.s3.raw_bucket_arn
  processed_bucket_arn      = module.s3.processed_bucket_arn
  glue_scripts_bucket_arn   = module.s3.glue_scripts_bucket_arn
  athena_results_bucket_arn = module.s3.athena_results_bucket_arn
  watermarks_table_arn      = module.dynamodb.watermarks_table_arn
}

module "networking" {
  source  = "./modules/networking"
  project = var.project
  env     = var.env
}

module "rds" {
  source  = "./modules/rds"
  project = var.project
  env     = var.env

  vpc_id                = module.networking.vpc_id
  subnet_ids            = module.networking.subnet_ids
  rds_security_group_id = module.networking.rds_security_group_id

  db_name     = var.db_name
  db_username = var.db_username
  db_password = var.db_password

  instance_class      = "db.t3.micro"
  allocated_storage   = 20
  multi_az            = false
  deletion_protection = false
}

module "glue" {
  source  = "./modules/glue"
  project = var.project
  env     = var.env

  glue_extraction_role_arn = module.iam.glue_extraction_role_arn
  glue_etl_role_arn        = module.iam.glue_etl_role_arn
  raw_bucket_id            = module.s3.raw_bucket_id
  processed_bucket_id      = module.s3.processed_bucket_id
  glue_scripts_bucket_id   = module.s3.glue_scripts_bucket_id

  create_jdbc_connection = true
  create_crawlers        = true

  rds_endpoint           = module.rds.endpoint
  rds_db_name            = var.db_name
  rds_username           = var.db_username
  rds_password           = var.db_password
  rds_availability_zone  = module.networking.first_subnet_az
  glue_security_group_id = module.networking.glue_security_group_id
  rds_subnet_id          = module.networking.first_subnet_id

  extraction_jobs = {
    "extract-orders" = {
      script_name = "extract_orders.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args = {
        "--extra-py-files" = "s3://${module.s3.glue_scripts_bucket_id}/libs/watermark.py,s3://${module.s3.glue_scripts_bucket_id}/libs/secrets_helper.py"
      }
    }
    "extract-customers" = {
      script_name = "extract_customers.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args = {
        "--extra-py-files" = "s3://${module.s3.glue_scripts_bucket_id}/libs/watermark.py,s3://${module.s3.glue_scripts_bucket_id}/libs/secrets_helper.py"
      }
    }
    "extract-products" = {
      script_name = "extract_products.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args = {
        "--extra-py-files" = "s3://${module.s3.glue_scripts_bucket_id}/libs/watermark.py,s3://${module.s3.glue_scripts_bucket_id}/libs/secrets_helper.py"
      }
    }
    "extract-payments" = {
      script_name = "extract_payments.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args = {
        "--extra-py-files" = "s3://${module.s3.glue_scripts_bucket_id}/libs/watermark.py,s3://${module.s3.glue_scripts_bucket_id}/libs/secrets_helper.py"
      }
    }
    "extract-page-views" = {
      script_name = "extract_page_views.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args = {
        "--extra-py-files" = "s3://${module.s3.glue_scripts_bucket_id}/libs/watermark.py,s3://${module.s3.glue_scripts_bucket_id}/libs/secrets_helper.py"
      }
    }
  }

  etl_jobs = {
    "bronze-to-silver-orders" = {
      script_name = "orders_silver.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
    "bronze-to-silver-customers" = {
      script_name = "customers_silver.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
    "bronze-to-silver-products" = {
      script_name = "products_silver.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
    "bronze-to-silver-payments" = {
      script_name = "payments_silver.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
    "silver-to-gold-daily-sales" = {
      script_name = "daily_sales.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
    "silver-to-gold-customer-ltv" = {
      script_name = "customer_ltv.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
    "silver-to-gold-top-products" = {
      script_name = "top_products.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
    "silver-to-gold-funnel" = {
      script_name = "funnel_analysis.py"
      num_workers = 2
      worker_type = "G.1X"
      extra_args  = {}
    }
  }
}

module "athena" {
  source  = "./modules/athena"
  project = var.project
  env     = var.env

  results_bucket_id    = module.s3.athena_results_bucket_id
  bytes_scanned_cutoff = 1073741824
}

module "step_functions" {
  source  = "./modules/step_functions"
  project = var.project
  env     = var.env

  step_functions_role_arn  = module.iam.step_functions_role_arn
  state_machine_definition = templatefile("${path.module}/../orchestration/step_functions/pipeline_definition.json.tftpl", {
    project = var.project
    env     = var.env
  })
}

module "monitoring" {
  source  = "./modules/monitoring"
  project = var.project
  env     = var.env

  alert_email = var.alert_email

  glue_job_names = [
    "extract-orders",
    "extract-customers",
    "extract-products",
    "extract-payments",
    "extract-page-views",
    "bronze-to-silver-orders",
    "bronze-to-silver-customers",
    "bronze-to-silver-products",
    "bronze-to-silver-payments",
    "silver-to-gold-daily-sales",
    "silver-to-gold-customer-ltv",
    "silver-to-gold-top-products",
    "silver-to-gold-funnel",
  ]

  aws_region        = var.aws_region
  state_machine_arn = module.step_functions.state_machine_arn
}

resource "aws_iam_role" "eventbridge_sfn" {
  name = "${var.project}-${var.env}-eventbridge-sfn"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Phase       = "6"
  }
}

resource "aws_iam_role_policy" "eventbridge_sfn" {
  name = "${var.project}-${var.env}-eventbridge-sfn"
  role = aws_iam_role.eventbridge_sfn.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "states:StartExecution"
        Resource = module.step_functions.state_machine_arn
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "pipeline_schedule" {
  name                = "${var.project}-${var.env}-pipeline-schedule"
  schedule_expression = "cron(0 3 * * ? *)"

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Phase       = "6"
  }
}

resource "aws_cloudwatch_event_target" "pipeline_schedule" {
  rule     = aws_cloudwatch_event_rule.pipeline_schedule.name
  arn      = module.step_functions.state_machine_arn
  role_arn = aws_iam_role.eventbridge_sfn.arn

  input = jsonencode({
    snsTopicArn = module.monitoring.alert_sns_topic_arn
  })
}
