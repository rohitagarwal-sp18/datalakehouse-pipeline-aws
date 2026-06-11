data "aws_caller_identity" "current" {}

locals {
  prefix        = "${var.project}-${var.env}"
  account_suffix = data.aws_caller_identity.current.account_id
  tags = merge(
    {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
    },
    var.tags
  )
}

# ─── RAW BUCKET (Bronze layer) ───────────────────────────────────────────────

resource "aws_s3_bucket" "raw" {
  bucket = "${local.prefix}-raw-${local.account_suffix}"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "raw" {
  bucket = aws_s3_bucket.raw.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {
  bucket                  = aws_s3_bucket.raw.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "archive-bronze"
    status = "Enabled"
    filter {}
    transition {
      days          = var.raw_lifecycle_ia_days
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = var.raw_lifecycle_glacier_days
      storage_class = "GLACIER"
    }
  }
}

# ─── PROCESSED BUCKET (Silver + Gold layers) ─────────────────────────────────

resource "aws_s3_bucket" "processed" {
  bucket = "${local.prefix}-processed-${local.account_suffix}"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "processed" {
  bucket = aws_s3_bucket.processed.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed" {
  bucket = aws_s3_bucket.processed.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "processed" {
  bucket                  = aws_s3_bucket.processed.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─── ATHENA RESULTS BUCKET ───────────────────────────────────────────────────

resource "aws_s3_bucket" "athena_results" {
  bucket = "${local.prefix}-athena-results-${local.account_suffix}"
  tags   = local.tags
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket                  = aws_s3_bucket.athena_results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id
  rule {
    id     = "expire-query-results"
    status = "Enabled"
    filter {}
    expiration { days = var.athena_results_expiry_days }
  }
}

# ─── GLUE SCRIPTS BUCKET ─────────────────────────────────────────────────────

resource "aws_s3_bucket" "glue_scripts" {
  bucket = "${local.prefix}-glue-scripts-${local.account_suffix}"
  tags   = local.tags
}

resource "aws_s3_bucket_versioning" "glue_scripts" {
  bucket = aws_s3_bucket.glue_scripts.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "glue_scripts" {
  bucket = aws_s3_bucket.glue_scripts.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "glue_scripts" {
  bucket                  = aws_s3_bucket.glue_scripts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
