import sys
from datetime import datetime, timezone

import pyspark.sql.functions as F
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

from watermark import get_watermark, update_watermark
from secrets_helper import get_rds_credentials

args = getResolvedOptions(sys.argv, ["JOB_NAME", "RAW_BUCKET", "WATERMARKS_TABLE", "ENV"])

sc = SparkContext()
glue_context = GlueContext(sc)
spark = glue_context.spark_session
job = Job(glue_context)
job.init(args["JOB_NAME"], args)

wm = get_watermark("orders", args["WATERMARKS_TABLE"])
creds = get_rds_credentials(f"datalakehouse-{args['ENV']}-rds-credentials")

now_utc = datetime.now(timezone.utc)
upper_bound = now_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00')

query = f"(SELECT * FROM orders WHERE created_at > '{wm}' AND created_at <= '{upper_bound}') AS orders_extract"

jdbc_url = f"jdbc:postgresql://{creds['host']}:{creds['port']}/{creds['dbname']}"

df = spark.read.jdbc(
    url=jdbc_url,
    table=query,
    properties={
        "user": creds["username"],
        "password": creds["password"],
        "driver": "org.postgresql.Driver",
    },
)

row_count = df.count()

if row_count == 0:
    print(f"[extract_orders] No new rows found between watermark={wm} and upper_bound={upper_bound}. Skipping write.")
    job.commit()
    sys.exit(0)

year = now_utc.year
month = now_utc.month
day = now_utc.day
raw_bucket = args["RAW_BUCKET"]

path = f"s3://{raw_bucket}/bronze/orders/year={year}/month={month:02d}/day={day:02d}/"

df.coalesce(1).write.mode("overwrite").option("header", "true").csv(path)

max_ts = df.agg(F.max("created_at")).collect()[0][0].strftime('%Y-%m-%dT%H:%M:%S+00:00')

update_watermark("orders", args["WATERMARKS_TABLE"], max_ts)

print(f"[extract_orders] row_count={row_count}")
print(f"[extract_orders] watermark_range={wm} -> {max_ts}")
print(f"[extract_orders] output_path={path}")

job.commit()
