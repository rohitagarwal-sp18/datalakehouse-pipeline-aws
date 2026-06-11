import sys
import logging
from datetime import datetime, timezone

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext

sys.path.insert(0, "/tmp/pipeline")
from pipeline.utils.watermark import get_watermark, update_watermark
from pipeline.utils.secrets_helper import get_rds_credentials

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = "page_views"
WATERMARK_KEY = "page_views"
BRONZE_PREFIX = "bronze/page_views"

REQUIRED_ARGS = [
    "JOB_NAME",
    "raw_bucket",
    "dynamodb_table",
    "secret_name",
    "environment",
]


def build_jdbc_url(host: str, port: str, dbname: str) -> str:
    return f"jdbc:postgresql://{host}:{port}/{dbname}"


def extract_page_views(
    glue_context: GlueContext,
    jdbc_url: str,
    username: str,
    password: str,
    watermark_ts: str,
    upper_bound_ts: str,
) -> "pyspark.sql.DataFrame":
    query = (
        f"(SELECT * FROM {TABLE_NAME} "
        f"WHERE created_at > '{watermark_ts}' "
        f"AND created_at <= '{upper_bound_ts}') AS page_views_extract"
    )
    logger.info("Extracting page_views with query filter: created_at > %s AND created_at <= %s", watermark_ts, upper_bound_ts)
    df = (
        glue_context.spark_session.read.format("jdbc")
        .option("url", jdbc_url)
        .option("dbtable", query)
        .option("user", username)
        .option("password", password)
        .option("driver", "org.postgresql.Driver")
        .option("fetchsize", "10000")
        .load()
    )
    return df


def build_s3_path(raw_bucket: str, now: datetime) -> str:
    return (
        f"s3://{raw_bucket}/{BRONZE_PREFIX}/"
        f"year={now.year}/"
        f"month={now.month:02d}/"
        f"day={now.day:02d}/"
    )


def main() -> None:
    args = getResolvedOptions(sys.argv, REQUIRED_ARGS)

    sc = SparkContext()
    glue_context = GlueContext(sc)
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    job_run_id = args.get("JOB_RUN_ID", "local")
    raw_bucket = args["raw_bucket"]
    dynamodb_table = args["dynamodb_table"]
    secret_name = args["secret_name"]

    now_utc = datetime.now(tz=timezone.utc)
    upper_bound_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    logger.info("Job started. Job run ID: %s", job_run_id)
    logger.info("Upper bound timestamp: %s", upper_bound_ts)

    credentials = get_rds_credentials(secret_name)
    jdbc_url = build_jdbc_url(
        host=credentials["host"],
        port=str(credentials["port"]),
        dbname=credentials["dbname"],
    )

    watermark_ts = get_watermark(
        table_name=WATERMARK_KEY,
        dynamodb_table=dynamodb_table,
    )
    logger.info("Watermark (lower bound): %s", watermark_ts)

    df = extract_page_views(
        glue_context=glue_context,
        jdbc_url=jdbc_url,
        username=credentials["username"],
        password=credentials["password"],
        watermark_ts=watermark_ts,
        upper_bound_ts=upper_bound_ts,
    )

    row_count = df.count()
    logger.info("Extracted %d rows from %s", row_count, TABLE_NAME)

    if row_count == 0:
        logger.info("No new rows to write. Skipping S3 write and watermark update.")
        job.commit()
        return

    s3_output_path = build_s3_path(raw_bucket=raw_bucket, now=now_utc)
    output_path = f"{s3_output_path}{job_run_id}.csv"
    logger.info("Writing CSV to: %s", output_path)

    df.coalesce(1).write.mode("overwrite").option("header", "true").csv(output_path)
    logger.info("S3 write complete.")

    max_created_at = df.agg({"created_at": "max"}).collect()[0][0]
    if max_created_at is not None:
        new_watermark = max_created_at.strftime("%Y-%m-%dT%H:%M:%S+00:00") if hasattr(max_created_at, "strftime") else str(max_created_at)
        update_watermark(
            table_name=WATERMARK_KEY,
            dynamodb_table=dynamodb_table,
            timestamp=new_watermark,
        )
        logger.info("Watermark updated to: %s", new_watermark)
    else:
        logger.warning("max(created_at) was None after non-zero count — watermark not updated.")

    job.commit()
    logger.info("Job committed successfully.")


if __name__ == "__main__":
    main()
