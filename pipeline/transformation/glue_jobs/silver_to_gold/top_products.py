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
GOLD_OUTPUT_PATH = f"s3://{PROCESSED_BUCKET}/gold/top_products/"


def read_catalog_or_s3(database: str, table_name: str, s3_fallback: str):
    try:
        df = glueContext.create_dynamic_frame.from_catalog(database=database, table_name=table_name).toDF()
        if not df.rdd.isEmpty():
            return df
    except Exception as exc:
        logger.warn(f"top_products: catalog read {database}.{table_name} failed: {exc}")
    return spark.read.format("parquet").load(s3_fallback)


order_items_df = read_catalog_or_s3(
    SILVER_DB, "order_items", f"s3://{PROCESSED_BUCKET}/silver/order_items/"
).select(
    F.col("product_id").cast("string"),
    F.col("order_id").cast("string"),
    F.col("quantity").cast("integer"),
    F.col("unit_price").cast("decimal(10,2)"),
)

products_df = read_catalog_or_s3(
    SILVER_DB, "products", f"s3://{PROCESSED_BUCKET}/silver/products/"
).select(
    F.col("id").cast("string").alias("product_id"),
    F.col("name").cast("string").alias("product_name"),
    F.col("category").cast("string"),
)

logger.info(f"top_products: order_items={order_items_df.count()} products={products_df.count()}")

gold_df = (
    order_items_df
    .groupBy("product_id")
    .agg(
        F.sum("quantity").cast("integer").alias("units_sold"),
        F.sum(F.col("quantity") * F.col("unit_price")).cast("decimal(18,2)").alias("total_revenue"),
        F.countDistinct("order_id").cast("integer").alias("order_count"),
        F.avg("unit_price").cast("decimal(10,4)").alias("avg_unit_price"),
    )
    .join(products_df, on="product_id", how="left")
    .select("product_id", "product_name", "category", "units_sold", "total_revenue", "order_count", "avg_unit_price")
    .orderBy(F.col("total_revenue").desc())
)

gold_df.write.format("parquet").option("compression", "snappy").mode("overwrite").save(GOLD_OUTPUT_PATH)

logger.info(f"top_products: wrote {gold_df.count()} rows to {GOLD_OUTPUT_PATH}")

job.commit()
