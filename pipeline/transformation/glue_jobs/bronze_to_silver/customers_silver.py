"""
Glue ETL job: Bronze customers → Silver customers

Catalog table (Bronze) : customers   (registered by Glue Crawler from bronze/customers/)
Silver output path      : s3://{s3_processed_bucket}/silver/customers/
Partition scheme        : year / month  (customers grow slowly — no day partition)
Output format           : Parquet + Snappy

Steps
-----
1.  Parse Glue job arguments.
2.  Read the Bronze customers partition(s) from the Glue Data Catalog.
3.  Short-circuit and exit cleanly if the source DataFrame is empty.
4.  Apply column transformations:
      a. Cast id           → IntegerType
      b. Cast created_at   → TimestampType
      c. Cast updated_at   → TimestampType
      d. Lowercase + trim  email
      e. Trim              name
      f. Drop              password_hash  (must never reach Silver)
5.  Standardise nulls: coerce empty strings to null across all StringType columns.
6.  Deduplicate on primary key (id), keeping the row with the latest updated_at.
7.  Derive partition columns: year (IntegerType), month (IntegerType) from created_at.
8.  Write Parquet + Snappy to the Silver path, partitioned by year / month.
9.  Log row counts (before and after dedup) and output path.
10. Commit the Glue job.

Notes
-----
- Bronze CSV data carries all columns as strings; explicit casts are therefore required.
- password_hash is dropped as step 4f — it must not be persisted in any downstream layer.
- Dedup strategy: window over id ordered by updated_at DESC, keep row_number == 1.
  This is safe for incremental loads where the same user_id may appear in multiple
  Bronze partitions across different extraction runs.
- Silver write mode is "overwrite" at the partition level (partitionOverwriteMode=dynamic)
  so re-running for the same year/month is idempotent without touching other partitions.
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, TimestampType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CATALOG_DATABASE: str = "bronze_db"
CATALOG_TABLE: str = "customers"
SILVER_PREFIX: str = "silver/customers"
PRIMARY_KEY: str = "id"
DEDUP_ORDER_COL: str = "updated_at"

# ---------------------------------------------------------------------------
# Step 1 — Parse Glue job arguments
# ---------------------------------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "s3_processed_bucket",  # e.g. "datalakehouse-dev-processed"
        "bronze_database",      # override if needed; defaults to CATALOG_DATABASE
        "bronze_table",         # override if needed; defaults to CATALOG_TABLE
    ],
)

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
logger = glue_context.get_logger()

# Allow job-arg overrides for database / table names while keeping sensible defaults.
bronze_database: str = args.get("bronze_database", CATALOG_DATABASE)
bronze_table: str = args.get("bronze_table", CATALOG_TABLE)

s3_silver_path: str = f"s3://{args['s3_processed_bucket']}/{SILVER_PREFIX}"

logger.info(
    f"[customers_silver] starting | "
    f"source={bronze_database}.{bronze_table} | "
    f"destination={s3_silver_path}"
)

# ---------------------------------------------------------------------------
# Step 2 — Read Bronze customers from the Glue Data Catalog
# ---------------------------------------------------------------------------

raw_df: DataFrame = (
    glue_context.create_data_frame.from_catalog(
        database=bronze_database,
        table_name=bronze_table,
        transformation_ctx="read_bronze_customers",
    )
)

# ---------------------------------------------------------------------------
# Step 3 — Short-circuit if source is empty
# ---------------------------------------------------------------------------

raw_count: int = raw_df.count()
logger.info(f"[customers_silver] rows read from Bronze: {raw_count}")

if raw_count == 0:
    logger.info(
        "[customers_silver] Bronze source is empty — nothing to process. "
        "Skipping write."
    )
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)
    job.commit()
    sys.exit(0)

# ---------------------------------------------------------------------------
# Step 4 — Column transformations
# ---------------------------------------------------------------------------

# 4a / 4b / 4c — Type casts
# Bronze CSVs carry every column as string; casts are therefore unconditional.
typed_df: DataFrame = (
    raw_df
    .withColumn(PRIMARY_KEY, F.col(PRIMARY_KEY).cast(IntegerType()))
    .withColumn("created_at", F.col("created_at").cast(TimestampType()))
    .withColumn("updated_at", F.col("updated_at").cast(TimestampType()))
)

# 4d — email: lowercase, trim leading/trailing whitespace
typed_df = typed_df.withColumn(
    "email",
    F.trim(F.lower(F.col("email"))),
)

# 4e — name: trim leading/trailing whitespace
typed_df = typed_df.withColumn(
    "name",
    F.trim(F.col("name")),
)

# 4f — Drop password_hash — must NEVER persist in Silver or any downstream layer
if "password_hash" in typed_df.columns:
    typed_df = typed_df.drop("password_hash")
    logger.info("[customers_silver] password_hash column dropped.")
else:
    logger.info(
        "[customers_silver] password_hash column not present in source — "
        "nothing to drop (Bronze schema may already exclude it)."
    )

# ---------------------------------------------------------------------------
# Step 5 — Standardise nulls: empty string → null for all StringType columns
# ---------------------------------------------------------------------------

from pyspark.sql.types import StringType  # noqa: E402 — import after schema is resolved

string_cols = [
    field.name
    for field in typed_df.schema.fields
    if isinstance(field.dataType, StringType)
]

null_standardised_df: DataFrame = typed_df
for col_name in string_cols:
    null_standardised_df = null_standardised_df.withColumn(
        col_name,
        F.when(F.trim(F.col(col_name)) == "", None).otherwise(F.col(col_name)),
    )

logger.info(
    f"[customers_silver] null standardisation applied to columns: {string_cols}"
)

# ---------------------------------------------------------------------------
# Step 6 — Deduplicate on primary key (id)
#
# Strategy: within each id group, keep the row with the most recent updated_at.
# Rows with a null updated_at are ranked last (nulls last ordering).
# ---------------------------------------------------------------------------

dedup_window = Window.partitionBy(PRIMARY_KEY).orderBy(
    F.col(DEDUP_ORDER_COL).desc_nulls_last()
)

deduped_df: DataFrame = (
    null_standardised_df
    .withColumn("_row_num", F.row_number().over(dedup_window))
    .filter(F.col("_row_num") == 1)
    .drop("_row_num")
)

deduped_count: int = deduped_df.count()
duplicates_removed: int = raw_count - deduped_count
logger.info(
    f"[customers_silver] deduplication complete | "
    f"before={raw_count} | after={deduped_count} | "
    f"duplicates_removed={duplicates_removed}"
)

# ---------------------------------------------------------------------------
# Step 7 — Derive partition columns: year, month from created_at
#
# Per CLAUDE.md: customers/users partitioned by year/month only (no day).
# ---------------------------------------------------------------------------

partitioned_df: DataFrame = (
    deduped_df
    .withColumn("year", F.year(F.col("created_at")).cast(IntegerType()))
    .withColumn("month", F.month(F.col("created_at")).cast(IntegerType()))
)

# ---------------------------------------------------------------------------
# Step 8 — Write Parquet + Snappy to Silver, partitioned by year / month
#
# partitionOverwriteMode=dynamic ensures a re-run for one year/month partition
# does not touch other partitions already written.
# ---------------------------------------------------------------------------

(
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
)

(
    partitioned_df.write
    .mode("overwrite")
    .option("compression", "snappy")
    .partitionBy("year", "month")
    .parquet(s3_silver_path)
)

logger.info(f"[customers_silver] Parquet written to: {s3_silver_path}")

# ---------------------------------------------------------------------------
# Step 9 — Log summary
# ---------------------------------------------------------------------------

logger.info(
    f"[customers_silver] job summary | "
    f"source={bronze_database}.{bronze_table} | "
    f"rows_read={raw_count} | "
    f"rows_written={deduped_count} | "
    f"duplicates_removed={duplicates_removed} | "
    f"output={s3_silver_path}"
)

# ---------------------------------------------------------------------------
# Step 10 — Commit the Glue job
# ---------------------------------------------------------------------------

job = Job(glue_context)
job.init(args["JOB_NAME"], args)
job.commit()
logger.info("[customers_silver] job committed successfully.")
