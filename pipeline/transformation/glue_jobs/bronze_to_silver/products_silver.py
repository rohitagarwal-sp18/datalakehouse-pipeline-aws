"""
Glue ETL job: products Bronze CSV → Silver Parquet.

Pattern (per CLAUDE.md Bronze → Silver):
  1. Read Bronze partitions for the products table from the Glue Data Catalog.
  2. Apply per-column transformations:
       - Cast id        → IntegerType
       - Cast price     → DecimalType(10, 2)
       - Cast stock_qty → IntegerType
       - Cast created_at → TimestampType
       - Trim name, category, description
       - Replace empty-string description with None (null)
       - Drop exact duplicate rows
       - Deduplicate on primary key (id), keeping the most-recently created row
  3. Write Parquet + Snappy to Silver path (full-refresh overwrite, no partitionBy).
  4. Commit the job.

Products is a small, slowly changing dimension table.  Per the partitioning
strategy in CLAUDE.md, Silver products has no partition columns — the entire
table is written as a flat directory and replaced on every run (mode overwrite).
This avoids partition sprawl on a table that rarely gains more than a handful
of rows per day, and simplifies downstream Athena queries to a single scan.

Output path:
  s3://{processed_bucket}/silver/products/

Catalog:
  Database : silver_db
  Table    : products
"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql import Window

# ---------------------------------------------------------------------------
# Job constants
# ---------------------------------------------------------------------------

TABLE_NAME: str = "products"
CATALOG_DATABASE: str = "bronze_db"
CATALOG_TABLE: str = "products"

# ---------------------------------------------------------------------------
# Bootstrap Glue context
# ---------------------------------------------------------------------------

args = getResolvedOptions(
    sys.argv,
    [
        "JOB_NAME",
        "processed_bucket",   # e.g. datalakehouse-dev-processed
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

processed_bucket: str = args["processed_bucket"]

s3_output_path: str = f"s3://{processed_bucket}/silver/{TABLE_NAME}/"

# ---------------------------------------------------------------------------
# Step 1 — Read Bronze data from the Glue Data Catalog
#
# Reading via the catalog (not a raw S3 path) lets Glue automatically handle
# partition discovery and schema inference from the Bronze Crawler output.
# ---------------------------------------------------------------------------

logger.info(f"[{TABLE_NAME}] Reading Bronze catalog: {CATALOG_DATABASE}.{CATALOG_TABLE}")

bronze_df = glue_context.create_dynamic_frame.from_catalog(
    database=CATALOG_DATABASE,
    table_name=CATALOG_TABLE,
).toDF()

row_count_bronze: int = bronze_df.count()
logger.info(f"[{TABLE_NAME}] Bronze row count: {row_count_bronze}")

if row_count_bronze == 0:
    logger.info(f"[{TABLE_NAME}] Bronze layer is empty. Nothing to transform. Exiting.")
    job.commit()
    sys.exit(0)

# ---------------------------------------------------------------------------
# Step 2 — Transformations
# ---------------------------------------------------------------------------

# --- 2a. Cast columns to correct types ------------------------------------- #
#
# Bronze CSV writes everything as strings.  Cast each column to its
# production type and let PySpark propagate nulls for unparseable values
# rather than raising exceptions (the default Spark behavior with permissive
# mode is to return null on cast failure for numeric/timestamp types).

df = bronze_df.select(
    F.col("id").cast(T.IntegerType()).alias("id"),
    F.trim(F.col("name")).alias("name"),
    F.trim(F.col("category")).alias("category"),
    F.trim(F.col("description")).alias("description"),
    F.col("price").cast(T.DecimalType(10, 2)).alias("price"),
    F.col("stock_qty").cast(T.IntegerType()).alias("stock_qty"),
    F.col("created_at").cast(T.TimestampType()).alias("created_at"),
)

# --- 2b. Standardise nulls ------------------------------------------------- #
#
# Empty strings are not semantically meaningful in the description column.
# Replace them with null so downstream consumers can use IS NULL checks
# uniformly rather than having to test for both empty-string and null.
# name and category are required fields; they are trimmed but not nullified
# here — data quality checks (Phase 8) will catch true missing values.

df = df.withColumn(
    "description",
    F.when(F.col("description") == "", F.lit(None).cast(T.StringType()))
    .otherwise(F.col("description")),
)

# --- 2c. Drop exact duplicate rows ---------------------------------------- #
#
# An exact duplicate occurs when all column values are identical.  This guards
# against double-ingestion scenarios where the same CSV partition was landed
# twice in Bronze.

df = df.dropDuplicates()

# --- 2d. Deduplicate on primary key (id) ----------------------------------- #
#
# If multiple rows share the same id (e.g. a product was re-seeded or
# re-created with the same id across extraction windows), retain only the row
# with the latest created_at.  This makes the Silver layer consistent with a
# type-1 SCD (last-write-wins) which is appropriate for a product dimension.

window_latest = Window.partitionBy("id").orderBy(F.col("created_at").desc())

df = (
    df.withColumn("_row_num", F.row_number().over(window_latest))
    .filter(F.col("_row_num") == 1)
    .drop("_row_num")
)

row_count_silver: int = df.count()
logger.info(f"[{TABLE_NAME}] Silver row count after deduplication: {row_count_silver}")

# ---------------------------------------------------------------------------
# Step 3 — Write Parquet + Snappy to Silver (full overwrite, no partitions)
#
# Products is small enough that a single directory of Parquet files is more
# efficient than a partitioned layout.  mode("overwrite") replaces the entire
# Silver table on every run, keeping the layer current without accumulating
# stale partition directories.
# ---------------------------------------------------------------------------

logger.info(f"[{TABLE_NAME}] Writing Silver Parquet to: {s3_output_path}")

(
    df.write
    .mode("overwrite")
    .option("compression", "snappy")
    .parquet(s3_output_path)
)

logger.info(f"[{TABLE_NAME}] Silver write complete.")

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

logger.info(
    f"[{TABLE_NAME}] Bronze → Silver complete. "
    f"Bronze rows: {row_count_bronze}, "
    f"Silver rows: {row_count_silver}, "
    f"Output: {s3_output_path}"
)

job.commit()
