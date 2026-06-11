import json
import os
import sys
from datetime import datetime, timezone

import boto3
import great_expectations as ge
import pandas as pd
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ["JOB_NAME", "PROCESSED_BUCKET", "TABLE_NAME", "ENV"])

JOB_NAME = args["JOB_NAME"]
PROCESSED_BUCKET = args["PROCESSED_BUCKET"]
TABLE_NAME = args["TABLE_NAME"]
ENV = args["ENV"]

print(f"[{JOB_NAME}] quality check | table={TABLE_NAME} env={ENV}")

s3_path = f"s3://{PROCESSED_BUCKET}/silver/{TABLE_NAME}/"
df = pd.read_parquet(s3_path)
print(f"[{JOB_NAME}] loaded {len(df):,} rows from {s3_path}")

ge_df = ge.from_pandas(df)

suite_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suites", f"{TABLE_NAME}_suite.json")
with open(suite_path, "r") as fh:
    suite = json.load(fh)

results = ge_df.validate(expectation_suite=suite, result_format="SUMMARY")

run_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
results_key = f"quality/{TABLE_NAME}/run_id={run_id}/results.json"

boto3.client("s3").put_object(
    Bucket=PROCESSED_BUCKET,
    Key=results_key,
    Body=json.dumps(results.to_json_dict(), indent=2),
    ContentType="application/json",
)

stats = results.statistics
print(
    f"[{JOB_NAME}] evaluated={stats['evaluated_expectations']} "
    f"successful={stats['successful_expectations']} "
    f"failed={stats['unsuccessful_expectations']} "
    f"success_pct={stats['success_percent']:.1f}%"
)

for exp_result in results.results:
    status = "PASS" if exp_result.success else "FAIL"
    exp_type = exp_result.expectation_config.expectation_type
    col = exp_result.expectation_config.kwargs.get("column", "<table>")
    print(f"  [{status}] {exp_type} | column={col}")

if not results["success"]:
    raise Exception(
        f"Quality check failed for {TABLE_NAME}: "
        f"{stats['unsuccessful_expectations']} expectation(s) failed. "
        f"Results: s3://{PROCESSED_BUCKET}/{results_key}"
    )

print(f"[{JOB_NAME}] all quality checks passed for {TABLE_NAME}")
