import sys
from datetime import datetime, timedelta, timezone

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, IntegerType, TimestampType

args_required = ["JOB_NAME", "PROCESSED_BUCKET", "BRONZE_DB", "SILVER_DB", "ENV"]

try:
    args = getResolvedOptions(sys.argv, args_required + ["PARTITION_DATE"])
    partition_date_str = args["PARTITION_DATE"]
except Exception:
    args = getResolvedOptions(sys.argv, args_required)
    partition_date_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

partition_date = datetime.strptime(partition_date_str, "%Y-%m-%d")
year = partition_date.year
month = partition_date.month
day = partition_date.day

sc = SparkContext()
sc._jsc.hadoopConfiguration().set("hive.metastore.client.factory.class", "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory")
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

logger = glueContext.get_logger()

logger.info(f"orders_silver: reading partition year={year} month={month} day={day} from {args['BRONZE_DB']}.orders")

df = glueContext.create_dynamic_frame.from_catalog(
    database=args["BRONZE_DB"],
    table_name="orders",
    push_down_predicate=f"year == {year} and month == {month} and day == {day}",
    additional_options={"useS3ListImplementation": True},
).toDF()

row_count = df.count()

if row_count == 0:
    logger.info("orders_silver: no rows found for partition — exiting without writing")
    job.commit()
    sys.exit(0)

logger.info(f"orders_silver: {row_count} raw rows read from Bronze")

df = (
    df
    .withColumn("id", F.col("id").cast(IntegerType()))
    .withColumn("user_id", F.col("user_id").cast(IntegerType()))
    .withColumn("subtotal", F.col("subtotal").cast(DecimalType(10, 2)))
    .withColumn("tax", F.col("tax").cast(DecimalType(10, 2)))
    .withColumn("total", F.col("total").cast(DecimalType(10, 2)))
    .withColumn("created_at", F.col("created_at").cast(TimestampType()))
    .withColumn("updated_at", F.col("updated_at").cast(TimestampType()))
    .withColumn("status", F.lower(F.trim(F.col("status"))))
    .withColumn(
        "shipping_address",
        F.when(F.trim(F.col("shipping_address")) == "", None).otherwise(F.trim(F.col("shipping_address"))),
    )
)

df = df.dropDuplicates(["id"])

df = (
    df
    .withColumn("year", F.year(F.col("created_at")))
    .withColumn("month", F.month(F.col("created_at")))
    .withColumn("day", F.dayofmonth(F.col("created_at")))
)

total_count = df.count()
distinct_id_count = df.select("id").distinct().count()

if total_count != distinct_id_count:
    logger.warn(
        f"orders_silver: id uniqueness violation after dedup — total={total_count} distinct_ids={distinct_id_count}"
    )

output_path = f"s3://{args['PROCESSED_BUCKET']}/silver/orders/"

df.write.mode("overwrite").partitionBy("year", "month", "day").option("compression", "snappy").parquet(output_path)

logger.info(
    f"orders_silver: wrote {total_count} rows to {output_path} partition year={year}/month={month}/day={day}"
)

job.commit()
