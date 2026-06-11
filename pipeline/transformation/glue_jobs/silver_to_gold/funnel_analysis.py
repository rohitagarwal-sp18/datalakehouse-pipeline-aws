import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType

args = getResolvedOptions(sys.argv, ["JOB_NAME", "PROCESSED_BUCKET", "SILVER_DB", "GOLD_DB", "ENV"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
logger = glueContext.get_logger()
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

PROCESSED_BUCKET = args["PROCESSED_BUCKET"]
SILVER_DB = args["SILVER_DB"]

page_views_df = glueContext.create_dynamic_frame.from_catalog(database=SILVER_DB, table_name="page_views").toDF()
orders_df = glueContext.create_dynamic_frame.from_catalog(database=SILVER_DB, table_name="orders").toDF()

logger.info(f"funnel_analysis: page_views={page_views_df.count()} orders={orders_df.count()}")

pv_metrics = (
    page_views_df
    .withColumn("event_date", F.to_date(F.col("created_at")))
    .groupBy("event_date")
    .agg(
        F.countDistinct("session_id").alias("unique_sessions"),
        F.count(F.when(F.col("path").startswith("/products/"), F.lit(1))).alias("product_views"),
        F.count(F.when(F.col("path") == "/cart", F.lit(1))).alias("cart_views"),
    )
)

order_metrics = (
    orders_df
    .withColumn("event_date", F.to_date(F.col("created_at")))
    .groupBy("event_date")
    .agg(
        F.count("id").alias("total_orders"),
        F.sum("total").alias("total_revenue"),
    )
)

gold_df = (
    pv_metrics
    .join(order_metrics, on="event_date", how="left")
    .fillna({"total_orders": 0, "total_revenue": 0.0})
    .withColumn(
        "cart_to_purchase_rate",
        F.when(F.col("cart_views").isNull() | (F.col("cart_views") == 0), F.lit(None).cast(DoubleType()))
        .otherwise(F.col("total_orders").cast(DoubleType()) / F.col("cart_views").cast(DoubleType())),
    )
    .withColumn(
        "product_to_cart_rate",
        F.when(F.col("product_views").isNull() | (F.col("product_views") == 0), F.lit(None).cast(DoubleType()))
        .otherwise(F.col("cart_views").cast(DoubleType()) / F.col("product_views").cast(DoubleType())),
    )
    .withColumn("year", F.year("event_date"))
    .withColumn("month", F.month("event_date"))
)

output_path = f"s3://{PROCESSED_BUCKET}/gold/funnel_analysis/"
gold_df.write.mode("overwrite").option("compression", "snappy").partitionBy("year", "month").parquet(output_path)

logger.info(f"funnel_analysis: wrote {gold_df.count()} rows to {output_path}")

job.commit()
