import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F

args = getResolvedOptions(sys.argv, ["JOB_NAME", "PROCESSED_BUCKET", "SILVER_DB", "GOLD_DB", "ENV"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
logger = glueContext.get_logger()
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

PROCESSED_BUCKET = args["PROCESSED_BUCKET"]
SILVER_DB = args["SILVER_DB"]

orders_df = glueContext.create_dynamic_frame.from_catalog(
    database=SILVER_DB, table_name="orders"
).toDF()

payments_df = glueContext.create_dynamic_frame.from_catalog(
    database=SILVER_DB, table_name="payments"
).toDF()

logger.info(f"daily_sales: orders={orders_df.count()} payments={payments_df.count()}")

joined_df = orders_df.alias("o").join(
    payments_df.alias("p"),
    on=F.col("o.id") == F.col("p.order_id"),
    how="left",
)

gold_df = (
    joined_df
    .groupBy(F.date_trunc("day", F.col("o.created_at")).cast("date").alias("sale_date"))
    .agg(
        F.countDistinct(F.col("o.id")).alias("total_orders"),
        F.sum(F.col("o.total")).alias("total_revenue"),
        F.avg(F.col("o.total")).alias("avg_order_value"),
        F.count(F.when(F.col("p.status") == "completed", F.col("p.id"))).alias("completed_payments"),
        F.sum(F.when(F.col("p.status") == "completed", F.col("p.amount")).otherwise(F.lit(0))).alias("total_paid"),
    )
    .withColumn("year", F.year("sale_date").cast("string"))
    .withColumn("month", F.lpad(F.month("sale_date").cast("string"), 2, "0"))
    .withColumn("day", F.lpad(F.dayofmonth("sale_date").cast("string"), 2, "0"))
)

output_path = f"s3://{PROCESSED_BUCKET}/gold/daily_sales/"
gold_df.write.mode("overwrite").partitionBy("year", "month", "day").option("compression", "snappy").parquet(output_path)

logger.info(f"daily_sales: wrote {gold_df.count()} rows to {output_path}")

job.commit()
