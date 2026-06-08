# ─────────────────────────────────────────────────────────────────────────────
# ROOT TERRAFORM CONFIG — wires all modules together
#
# Phase-gated: resources for later phases are commented out with clear labels.
# Uncomment each section as you progress through the build phases.
# ─────────────────────────────────────────────────────────────────────────────

# ─── PHASE 1: S3 BUCKETS ─────────────────────────────────────────────────────

module "s3" {
  source  = "./modules/s3"
  project = var.project
  env     = var.env
}

# ─── PHASE 1: DYNAMODB WATERMARKS ────────────────────────────────────────────

module "dynamodb" {
  source  = "./modules/dynamodb"
  project = var.project
  env     = var.env
}

# ─── PHASE 1: IAM ROLES ──────────────────────────────────────────────────────

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

# ─── PHASE 1: GLUE CATALOG DATABASES ─────────────────────────────────────────

module "glue" {
  source  = "./modules/glue"
  project = var.project
  env     = var.env

  glue_extraction_role_arn = module.iam.glue_extraction_role_arn
  glue_etl_role_arn        = module.iam.glue_etl_role_arn
  raw_bucket_id            = module.s3.raw_bucket_id
  processed_bucket_id      = module.s3.processed_bucket_id
  glue_scripts_bucket_id   = module.s3.glue_scripts_bucket_id

  # Phase 3: set to true and fill in RDS connection vars below
  create_jdbc_connection = false
  create_crawlers        = false
  extraction_jobs        = {}
  etl_jobs               = {}

  # Phase 3: uncomment and fill in when RDS module is enabled
  # rds_endpoint           = module.rds.endpoint
  # rds_db_name            = var.db_name
  # rds_username           = var.db_username
  # rds_password           = var.db_password
  # rds_availability_zone  = module.networking.first_subnet_az
  # glue_security_group_id = module.networking.glue_security_group_id
  # rds_subnet_id          = module.networking.first_subnet_id

  # Phase 3: uncomment when extraction scripts are uploaded to S3
  # extraction_jobs = {
  #   "extract-orders" = {
  #     script_name = "extract_orders.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "extract-customers" = {
  #     script_name = "extract_customers.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "extract-products" = {
  #     script_name = "extract_products.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "extract-payments" = {
  #     script_name = "extract_payments.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "extract-page-views" = {
  #     script_name = "extract_page_views.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  # }

  # Phase 4: uncomment when ETL scripts are uploaded to S3
  # etl_jobs = {
  #   "bronze-to-silver-orders" = {
  #     script_name = "orders_silver.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "bronze-to-silver-customers" = {
  #     script_name = "customers_silver.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "bronze-to-silver-payments" = {
  #     script_name = "payments_silver.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "silver-to-gold-daily-sales" = {
  #     script_name = "daily_sales.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  #   "silver-to-gold-customer-ltv" = {
  #     script_name = "customer_ltv.py"
  #     num_workers = 2
  #     worker_type = "G.1X"
  #     extra_args  = {}
  #   }
  # }
}

# ─── PHASE 1: ATHENA WORKGROUP ───────────────────────────────────────────────

module "athena" {
  source  = "./modules/athena"
  project = var.project
  env     = var.env

  results_bucket_id    = module.s3.athena_results_bucket_id
  bytes_scanned_cutoff = 1073741824 # 1 GB safety limit per query
}

# ─── PHASE 2: NETWORKING + RDS ───────────────────────────────────────────────
# Uncomment when building the e-commerce app

# module "networking" {
#   source  = "./modules/networking"
#   project = var.project
#   env     = var.env
# }
#
# module "rds" {
#   source  = "./modules/rds"
#   project = var.project
#   env     = var.env
#
#   vpc_id                = module.networking.vpc_id
#   subnet_ids            = module.networking.subnet_ids
#   rds_security_group_id = module.networking.rds_security_group_id
#
#   db_name     = var.db_name
#   db_username = var.db_username
#   db_password = var.db_password
#
#   instance_class      = "db.t3.micro"
#   allocated_storage   = 20
#   multi_az            = false
#   deletion_protection = false
# }

# ─── PHASE 6: STEP FUNCTIONS ─────────────────────────────────────────────────
# Uncomment after writing the ASL pipeline definition

# module "step_functions" {
#   source  = "./modules/step_functions"
#   project = var.project
#   env     = var.env
#
#   step_functions_role_arn  = module.iam.step_functions_role_arn
#   state_machine_definition = file("${path.module}/../orchestration/step_functions/pipeline_definition.json")
# }

# ─── PHASE 7: MONITORING ─────────────────────────────────────────────────────
# Uncomment after Glue jobs and Step Functions exist

# module "monitoring" {
#   source  = "./modules/monitoring"
#   project = var.project
#   env     = var.env
#
#   alert_email = var.alert_email
#
#   glue_job_names = [
#     "extract-orders",
#     "extract-customers",
#     "extract-payments",
#     "bronze-to-silver-orders",
#     "bronze-to-silver-customers",
#     "silver-to-gold-daily-sales",
#   ]
#
#   state_machine_arn = module.step_functions.state_machine_arn
# }
