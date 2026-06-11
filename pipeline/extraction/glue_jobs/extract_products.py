"""
Glue extraction job: products table → Bronze S3 layer.

Pattern:
  1. Read last watermark from DynamoDB.
  2. Open JDBC connection to RDS via credentials from Secrets Manager.
  3. SELECT * FROM products WHERE created_at > {watermark} AND created_at <= NOW()
  4. Write CSV to s3://{raw_bucket}/bronze/products/year=YYYY/month=MM/day=DD/{job_run_id}.csv
  5. Update DynamoDB watermark to max(created_at) from the extracted batch.

Products is a small, semi-static table.  The same incremental watermark
pattern is used so new and updated-by-recreation rows are captured correctly.
Watermark is keyed on `created_at`, consistent with all other extraction jobs.
"""

import sys
from datetime import datetime, timezone

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

sys.path.insert(0, "/tmp/pipeline_utils")

from pipeline.utils.secrets_helper import get_rds_credentials
from pipeline.utils.watermark import get_watermark, update_watermark

# ---------------------------------------------------------------------------
# Job constants
# ---------------------------------------------------------------------------

TABLE_NAME: str = "products"
WATERMARK_KEY: str = "products"

# ---------------------------------------------------------------------------
# Bootstrap Glue context
# ---------------------------------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "raw_bucket",           # e.g. datalakehouse-dev-raw
        "dynamodb_table",       # e.g. datalakehouse-dev-watermarks
        "secret_name",          # Secrets Manager secret for RDS credentials
        "rds_db_name",          # PostgreSQL database name
    ],
)

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
logger = glue_context.get_logger()

job = Job(glue_context)
job.init(args["JOB_NAME"], args)

# ---------------------------------------------------------------------------
# Resolve arguments
# ---------------------------------------------------------------------------

raw_bucket: str = args["raw_bucket"]
dynamodb_table: str = args["dynamodb_table"]
secret_name: str = args["secret_name"]
rds_db_name: str = args["rds_db_name"]
job_run_id: str = args["JOB_RUN_ID"]  # injected automatically by Glue

# ---------------------------------------------------------------------------
# Step 1 — Read watermark
# ---------------------------------------------------------------------------

watermark: str = get_watermark(WATERMARK_KEY, dynamodb_table)
logger.info(f"[{TABLE_NAME}] Last watermark: {watermark}")

# ---------------------------------------------------------------------------
# Step 2 — Resolve RDS connection details
# ---------------------------------------------------------------------------

creds = get_rds_credentials(secret_name)

jdbc_url = (
    f"jdbc:postgresql://{creds['host']}:{creds['port']}/{rds_db_name}"
)

# Use a closed upper bound to avoid extracting in-flight rows.
upper_bound: str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

sql_query = (
    f"(SELECT * FROM {TABLE_NAME} "
    f"WHERE created_at > '{watermark}' "
    f"AND created_at <= '{upper_bound}') AS extraction_query"
)

logger.info(f"[{TABLE_NAME}] Extraction query: {sql_query}")

# ---------------------------------------------------------------------------
# Step 3 — Extract via JDBC
# ---------------------------------------------------------------------------

df = (
    spark.read.format("jdbc")
    .option("url", jdbc_url)
    .option("dbtable", sql_query)
    .option("user", creds["username"])
    .option("password", creds["password"])
    .option("driver", "org.postgresql.Driver")
    .load()
)

row_count: int = df.count()
logger.info(f"[{TABLE_NAME}] Rows extracted: {row_count}")

if row_count == 0:
    logger.info(f"[{TABLE_NAME}] No new rows since watermark {watermark}. Exiting.")
    job.commit()
    sys.exit(0)

# ---------------------------------------------------------------------------
# Step 4 — Write CSV to Bronze S3 path
#
# Path structure: bronze/products/year=YYYY/month=MM/day=DD/{job_run_id}.csv
# Partition columns are derived from the upper_bound timestamp so all files
# written in this run land in a single deterministic partition.
# ---------------------------------------------------------------------------

run_dt = datetime.now(tz=timezone.utc)
year: str = run_dt.strftime("%Y")
month: str = run_dt.strftime("%m")
day: str = run_dt.strftime("%d")

s3_output_path = (
    f"s3://{raw_bucket}/bronze/{TABLE_NAME}/"
    f"year={year}/month={month}/day={day}/"
    f"{job_run_id}.csv"
)

logger.info(f"[{TABLE_NAME}] Writing to: {s3_output_path}")

# Coalesce to a single file per run — products table is small enough that
# one file per daily partition is appropriate and avoids small-file overhead.
(
    df.coalesce(1)
    .write.mode("append")
    .option("header", "true")
    .csv(s3_output_path)
)

logger.info(f"[{TABLE_NAME}] S3 write complete.")

# ---------------------------------------------------------------------------
# Step 5 — Update watermark to max(created_at) from this batch
#
# Watermark is updated AFTER the S3 write succeeds so the job is safely
# re-runnable on failure — re-running will re-extract and overwrite the
# partial CSV.
# ---------------------------------------------------------------------------

max_created_at: str = (
    df.select(F.max("created_at").alias("max_ts"))
    .collect()[0]["max_ts"]
    .strftime("%Y-%m-%dT%H:%M:%S+00:00")
)

update_watermark(WATERMARK_KEY, dynamodb_table, max_created_at)
logger.info(f"[{TABLE_NAME}] Watermark updated to: {max_created_at}")

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

logger.info(
    f"[{TABLE_NAME}] Extraction complete. "
    f"Rows: {row_count}, "
    f"Window: {watermark} → {max_created_at}, "
    f"Output: {s3_output_path}"
)

job.commit()
