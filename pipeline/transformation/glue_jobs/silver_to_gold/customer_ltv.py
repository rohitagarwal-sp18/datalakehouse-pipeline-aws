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

customers_df = glueContext.create_dynamic_frame.from_catalog(database=SILVER_DB, table_name="customers").toDF()
orders_df = glueContext.create_dynamic_frame.from_catalog(database=SILVER_DB, table_name="orders").toDF()
payments_df = glueContext.create_dynamic_frame.from_catalog(database=SILVER_DB, table_name="payments").toDF()

logger.info(f"customer_ltv: customers={customers_df.count()} orders={orders_df.count()} payments={payments_df.count()}")

completed_payments_df = payments_df.filter(F.col("status") == "completed")

orders_with_payments_df = orders_df.alias("o").join(
    completed_payments_df.alias("p"),
    on=F.col("o.id") == F.col("p.order_id"),
    how="left",
)

customer_orders_df = customers_df.alias("c").join(
    orders_with_payments_df,
    on=F.col("o.user_id") == F.col("c.id"),
    how="left",
)

gold_df = (
    customer_orders_df
    .groupBy(
        F.col("c.id").alias("customer_id"),
        F.col("c.email").alias("email"),
        F.col("c.name").alias("name"),
    )
    .agg(
        F.min(F.when(F.col("o.id").isNotNull(), F.col("o.created_at"))).alias("first_order_date"),
        F.max(F.when(F.col("o.id").isNotNull(), F.col("o.created_at"))).alias("last_order_date"),
        F.countDistinct(F.when(F.col("o.id").isNotNull(), F.col("o.id"))).alias("total_orders"),
        F.coalesce(F.sum(F.col("p.amount")), F.lit(0.0)).alias("total_revenue"),
    )
    .withColumn(
        "avg_order_value",
        F.when(F.col("total_orders") > 0, F.col("total_revenue") / F.col("total_orders").cast("double")).otherwise(F.lit(0.0)),
    )
    .withColumn(
        "days_as_customer",
        F.when(
            F.col("first_order_date").isNotNull() & F.col("last_order_date").isNotNull(),
            F.datediff(F.col("last_order_date"), F.col("first_order_date")),
        ).otherwise(F.lit(0)),
    )
    .withColumn("cohort_year", F.year(F.col("first_order_date")))
    .withColumn("cohort_month", F.month(F.col("first_order_date")))
    .select(
        "customer_id", "email", "name", "first_order_date", "last_order_date",
        "total_orders", "total_revenue", "avg_order_value", "days_as_customer",
        "cohort_year", "cohort_month",
    )
)

output_path = f"s3://{PROCESSED_BUCKET}/gold/customer_ltv/"
gold_df.write.format("parquet").option("compression", "snappy").mode("overwrite").partitionBy("cohort_year", "cohort_month").save(output_path)

logger.info(f"customer_ltv: wrote {gold_df.count()} rows to {output_path}")

job.commit()
