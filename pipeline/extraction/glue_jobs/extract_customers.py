"""
Glue extraction job: users table → Bronze S3 (pipeline key: customers)

Watermark key  : customers  (DynamoDB table_name PK)
Source table   : users      (app PostgreSQL / RDS)
Bronze prefix  : bronze/customers/year=YYYY/month=MM/day=DD/
Output format  : CSV (header row, UTF-8)

Steps
-----
1.  Parse Glue job arguments.
2.  Read the last watermark from DynamoDB.
3.  Compute the upper bound (NOW() in UTC — closed, prevents in-flight rows).
4.  Build the JDBC extraction query.
5.  Retrieve RDS credentials from Secrets Manager.
6.  Build the JDBC URL.
7.  Read data from RDS via Glue DynamicFrame (JDBC).
8.  Short-circuit and exit cleanly if no rows were returned.
9.  Compute the max created_at from the extracted batch.
10. Build the S3 output path (Hive-partitioned by year/month/day of upper bound).
11. Write CSV to S3 Bronze path (via Spark, single pass).
12. Log row count and time range covered.
13. Update the DynamoDB watermark to the max created_at from this batch.
14. Commit the Glue job.
"""

import sys
from datetime import datetime, timezone

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

from pipeline.utils.secrets_helper import get_rds_credentials
from pipeline.utils.watermark import get_watermark, update_watermark

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TABLE_NAME: str = "users"          # source table name in PostgreSQL
WATERMARK_KEY: str = "customers"   # DynamoDB partition key for this job's watermark
BRONZE_PREFIX: str = "bronze/customers"

# ---------------------------------------------------------------------------
# Step 1 — Parse Glue job arguments
# ---------------------------------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "dynamodb_table",       # e.g. "datalakehouse-dev-watermarks"
        "secret_name",          # e.g. "datalakehouse/dev/rds"
        "s3_raw_bucket",        # e.g. "datalakehouse-dev-raw"
        "db_name",              # e.g. "ecommerce"
    ],
)

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
logger = glue_context.get_logger()

# ---------------------------------------------------------------------------
# Step 2 — Read the last watermark from DynamoDB
# ---------------------------------------------------------------------------

watermark: str = get_watermark(
    table_name=WATERMARK_KEY,
    dynamodb_table=args["dynamodb_table"],
)
logger.info(f"[extract_customers] watermark read: {watermark}")

# ---------------------------------------------------------------------------
# Step 3 — Compute the upper bound (closed, UTC)
# ---------------------------------------------------------------------------

upper_bound: str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
logger.info(f"[extract_customers] upper_bound: {upper_bound}")

# ---------------------------------------------------------------------------
# Step 4 — Build the JDBC extraction query
# ---------------------------------------------------------------------------

query: str = (
    f"(SELECT * FROM {TABLE_NAME} "
    f"WHERE created_at > '{watermark}' "
    f"AND created_at <= '{upper_bound}') AS users_batch"
)
logger.info(f"[extract_customers] extraction query: {query}")

# ---------------------------------------------------------------------------
# Step 5 — Retrieve RDS credentials from Secrets Manager
# ---------------------------------------------------------------------------

credentials: dict = get_rds_credentials(secret_name=args["secret_name"])

# ---------------------------------------------------------------------------
# Step 6 — Build the JDBC URL
# ---------------------------------------------------------------------------

jdbc_url: str = (
    f"jdbc:postgresql://{credentials['host']}:{credentials['port']}"
    f"/{args['db_name']}"
)
logger.info(f"[extract_customers] jdbc_url (no creds): {jdbc_url}")

# ---------------------------------------------------------------------------
# Step 7 — Read data from RDS via Spark JDBC
# ---------------------------------------------------------------------------

df = (
    spark.read.format("jdbc")
    .option("url", jdbc_url)
    .option("dbtable", query)
    .option("user", credentials["username"])
    .option("password", credentials["password"])
    .option("driver", "org.postgresql.Driver")
    .load()
)

# ---------------------------------------------------------------------------
# Step 8 — Short-circuit if no rows were returned
# ---------------------------------------------------------------------------

row_count: int = df.count()
logger.info(f"[extract_customers] rows extracted: {row_count}")

if row_count == 0:
    logger.info(
        "[extract_customers] no new rows since watermark — skipping S3 write "
        "and watermark update."
    )
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)
    job.commit()
    sys.exit(0)

# ---------------------------------------------------------------------------
# Step 9 — Compute the max created_at from the extracted batch
# ---------------------------------------------------------------------------

max_created_at: str = (
    df.agg(F.max("created_at").alias("max_ts"))
    .collect()[0]["max_ts"]
    .strftime("%Y-%m-%dT%H:%M:%S+00:00")
)
logger.info(f"[extract_customers] max created_at in batch: {max_created_at}")

# ---------------------------------------------------------------------------
# Step 10 — Build the S3 output path (Hive-partitioned by upper-bound date)
# ---------------------------------------------------------------------------

upper_dt: datetime = datetime.strptime(upper_bound, "%Y-%m-%dT%H:%M:%S+00:00")
s3_output_path: str = (
    f"s3://{args['s3_raw_bucket']}/{BRONZE_PREFIX}"
    f"/year={upper_dt.year:04d}"
    f"/month={upper_dt.month:02d}"
    f"/day={upper_dt.day:02d}"
)
logger.info(f"[extract_customers] s3 output path: {s3_output_path}")

# ---------------------------------------------------------------------------
# Step 11 — Write CSV to S3 Bronze path
#   • header=True  — include column names in the CSV
#   • mode=append  — safe to re-run; each run writes a new file in the partition
# ---------------------------------------------------------------------------

df.write.mode("append").option("header", "true").csv(s3_output_path)
logger.info(f"[extract_customers] CSV written to: {s3_output_path}")

# ---------------------------------------------------------------------------
# Step 12 — Log row count and time range covered
# ---------------------------------------------------------------------------

logger.info(
    f"[extract_customers] extraction summary | "
    f"table={TABLE_NAME} | "
    f"watermark_key={WATERMARK_KEY} | "
    f"rows={row_count} | "
    f"window=[{watermark}, {upper_bound}] | "
    f"max_created_at={max_created_at} | "
    f"output={s3_output_path}"
)

# ---------------------------------------------------------------------------
# Step 13 — Update the DynamoDB watermark (only after confirmed S3 write)
# ---------------------------------------------------------------------------

update_watermark(
    table_name=WATERMARK_KEY,
    dynamodb_table=args["dynamodb_table"],
    timestamp=max_created_at,
)
logger.info(f"[extract_customers] watermark updated to: {max_created_at}")

# ---------------------------------------------------------------------------
# Step 14 — Commit the Glue job
# ---------------------------------------------------------------------------

job = Job(glue_context)
job.init(args["JOB_NAME"], args)
job.commit()
logger.info("[extract_customers] job committed successfully.")
