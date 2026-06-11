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

# ─── TRUST POLICIES ──────────────────────────────────────────────────────────

data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "states_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

# ─── GLUE EXTRACTION ROLE ────────────────────────────────────────────────────
# Used by JDBC extraction jobs: reads RDS, writes Bronze S3, updates DynamoDB watermarks

resource "aws_iam_role" "glue_extraction" {
  name               = "${local.prefix}-glue-extraction-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
  tags               = local.tags
}

data "aws_iam_policy_document" "glue_extraction" {
  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "S3RawWrite"
    actions = ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"]
    resources = ["${var.raw_bucket_arn}/*"]
  }

  statement {
    sid     = "S3RawList"
    actions = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [var.raw_bucket_arn]
  }

  statement {
    sid     = "S3GlueScripts"
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [var.glue_scripts_bucket_arn, "${var.glue_scripts_bucket_arn}/*"]
  }

  statement {
    sid = "DynamoDBWatermarks"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DescribeTable",
    ]
    resources = [var.watermarks_table_arn]
  }

  statement {
    sid = "GlueCatalogWrite"
    actions = [
      "glue:GetDatabase",
      "glue:GetTable",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:BatchCreatePartition",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:CreatePartition",
      "glue:UpdatePartition",
    ]
    resources = ["*"]
  }

  # Glue needs these EC2 permissions to create ENIs in the VPC for JDBC connections
  statement {
    sid = "GlueVpcNetworking"
    actions = [
      "ec2:DescribeVpcEndpoints",
      "ec2:DescribeRouteTables",
      "ec2:CreateNetworkInterface",
      "ec2:DeleteNetworkInterface",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSubnets",
      "ec2:DescribeVpcAttribute",
      "ec2:CreateTags",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "SecretsManager"
    actions = ["secretsmanager:GetSecretValue"]
    resources = ["arn:aws:secretsmanager:*:*:secret:${local.prefix}-rds-*"]
  }
}

resource "aws_iam_role_policy" "glue_extraction" {
  name   = "${local.prefix}-glue-extraction-policy"
  role   = aws_iam_role.glue_extraction.id
  policy = data.aws_iam_policy_document.glue_extraction.json
}

resource "aws_iam_role_policy_attachment" "glue_extraction_service" {
  role       = aws_iam_role.glue_extraction.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# ─── GLUE ETL ROLE ────────────────────────────────────────────────────────────
# Used by ETL jobs and crawlers: reads Bronze, writes Silver/Gold, manages catalog

resource "aws_iam_role" "glue_etl" {
  name               = "${local.prefix}-glue-etl-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
  tags               = local.tags
}

data "aws_iam_policy_document" "glue_etl" {
  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "S3RawRead"
    actions = ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [var.raw_bucket_arn, "${var.raw_bucket_arn}/*"]
  }

  statement {
    sid     = "S3ProcessedReadWrite"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [var.processed_bucket_arn, "${var.processed_bucket_arn}/*"]
  }

  statement {
    sid     = "S3GlueScriptsAndTemp"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
    resources = [var.glue_scripts_bucket_arn, "${var.glue_scripts_bucket_arn}/*"]
  }

  statement {
    sid = "GlueCatalogReadWrite"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:DeleteTable",
      "glue:BatchCreatePartition",
      "glue:CreatePartition",
      "glue:UpdatePartition",
      "glue:DeletePartition",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:BatchGetPartition",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "glue_etl" {
  name   = "${local.prefix}-glue-etl-policy"
  role   = aws_iam_role.glue_etl.id
  policy = data.aws_iam_policy_document.glue_etl.json
}

resource "aws_iam_role_policy_attachment" "glue_etl_service" {
  role       = aws_iam_role.glue_etl.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# ─── STEP FUNCTIONS ROLE ─────────────────────────────────────────────────────

resource "aws_iam_role" "step_functions" {
  name               = "${local.prefix}-step-functions-role"
  assume_role_policy = data.aws_iam_policy_document.states_assume_role.json
  tags               = local.tags
}

data "aws_iam_policy_document" "step_functions" {
  statement {
    sid = "GlueJobControl"
    actions = [
      "glue:StartJobRun",
      "glue:GetJobRun",
      "glue:GetJobRuns",
      "glue:BatchStopJobRun",
      "glue:StartCrawler",
      "glue:GetCrawler",
      "glue:StopCrawler",
    ]
    resources = ["*"]
  }

  statement {
    sid = "CloudWatchLogs"
    actions = [
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "SNSAlerts"
    actions = ["sns:Publish"]
    resources = ["arn:aws:sns:*:*:${local.prefix}-*"]
  }

  statement {
    sid = "XRayTracing"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "step_functions" {
  name   = "${local.prefix}-step-functions-policy"
  role   = aws_iam_role.step_functions.id
  policy = data.aws_iam_policy_document.step_functions.json
}
