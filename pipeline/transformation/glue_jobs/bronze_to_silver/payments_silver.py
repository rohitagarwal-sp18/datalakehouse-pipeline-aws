import sys

import pyspark.sql.functions as F
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql.types import DecimalType, IntegerType, TimestampType

args = getResolvedOptions(
    sys.argv,
    ["JOB_NAME", "RAW_BUCKET", "PROCESSED_BUCKET", "PARTITION_DATE"],
)
# PARTITION_DATE format: YYYY-MM-DD  (e.g. "2026-06-11")

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

partition_date = args["PARTITION_DATE"]
year, month, day = partition_date.split("-")

raw_bucket = args["RAW_BUCKET"]
processed_bucket = args["PROCESSED_BUCKET"]

bronze_path = (
    f"s3://{raw_bucket}/bronze/payments/"
    f"year={year}/month={month}/day={day}/"
)

print(f"[payments_silver] Reading Bronze from: {bronze_path}")

df = spark.read.option("header", "true").csv(bronze_path)

# ------------------------------------------------------------------
# Type casts
# ------------------------------------------------------------------
df = (
    df
    .withColumn("id", F.col("id").cast(IntegerType()))
    .withColumn("order_id", F.col("order_id").cast(IntegerType()))
    .withColumn("amount", F.col("amount").cast(DecimalType(10, 2)))
    .withColumn("created_at", F.col("created_at").cast(TimestampType()))
)

# ------------------------------------------------------------------
# String normalisations
# ------------------------------------------------------------------
df = (
    df
    .withColumn("status", F.lower(F.trim(F.col("status"))))
    .withColumn("method", F.lower(F.trim(F.col("method"))))
    .withColumn(
        "transaction_ref",
        F.when(
            F.trim(F.col("transaction_ref")) == "",
            F.lit(None).cast("string"),
        ).otherwise(F.trim(F.col("transaction_ref"))),
    )
)

# ------------------------------------------------------------------
# Deduplication — keep the first occurrence of each payment id
# ------------------------------------------------------------------
df = df.dropDuplicates(["id"])

# ------------------------------------------------------------------
# Partition columns derived from created_at
# ------------------------------------------------------------------
df = (
    df
    .withColumn("year", F.year(F.col("created_at")))
    .withColumn("month", F.month(F.col("created_at")))
    .withColumn("day", F.dayofmonth(F.col("created_at")))
)

row_count = df.count()
print(f"[payments_silver] row_count after transforms: {row_count}")

if row_count == 0:
    print("[payments_silver] No rows to write. Exiting cleanly.")
    job.commit()
    sys.exit(0)

# ------------------------------------------------------------------
# Write Silver — Parquet + Snappy, partitioned by year/month/day
# ------------------------------------------------------------------
silver_path = f"s3://{processed_bucket}/silver/payments/"

df.write.mode("overwrite").option("compression", "snappy").partitionBy(
    "year", "month", "day"
).parquet(silver_path)

print(f"[payments_silver] Written Silver to: {silver_path}")
print(f"[payments_silver] partition_date={partition_date} row_count={row_count}")

job.commit()
