# CLAUDE.md — Enterprise Data Lakehouse Pipeline on AWS

## What This Project Is

Two decoupled systems:

1. **E-commerce App** (`app/`) — standalone FastAPI + PostgreSQL web app. Has no knowledge of AWS or the data pipeline. Runs independently via Docker Compose.

2. **Data Pipeline** (`terraform/`, `pipeline/`) — AWS batch pipeline that extracts from the app's RDS database on a schedule, transforms data through Bronze → Silver → Gold, serves analytics via Athena.

User builds all code themselves. **Do not write code unless explicitly asked.**

---

## Core Constraints

- **No code unless explicitly asked.** Explain, design, advise only.
- **No console-click instructions.** Everything is Terraform or CLI.
- **No shortcuts.** Production-correct patterns even if harder.
- **No app + pipeline coupling.** App code must never import boto3, reference S3, or know about the pipeline.
- **One phase at a time.** Don't suggest Phase N+1 while Phase N is active.

---

## Tech Stack

### App

| Layer | Tech |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async) |
| Database | PostgreSQL 15 |
| Frontend | Jinja2 templates + Vanilla JS |
| Local dev | Docker Compose (app + postgres) |

### Pipeline (AWS)

| Layer | Tech |
|---|---|
| IaC | Terraform >= 1.6 |
| Extraction | AWS Glue (JDBC connection to RDS) |
| ETL | AWS Glue 4.0 + PySpark (Spark 3.3) |
| Orchestration | AWS Step Functions (Express workflows) |
| Storage | Amazon S3 (separate buckets by purpose) |
| Catalog | AWS Glue Data Catalog (one DB per layer) |
| Query | Amazon Athena v3 |
| App DB (cloud) | Amazon RDS PostgreSQL 15 |
| Watermarks | DynamoDB table (stores last extraction timestamp per table) |
| Monitoring | CloudWatch |
| Secrets | AWS Secrets Manager |
| Data Quality | Great Expectations |
| Formats | CSV (Bronze), Parquet/Snappy (Silver + Gold) |
| CI/CD | GitHub Actions |

---

## Project Phases

### Phase 1 — Foundation
**Goal:** Complete AWS skeleton via Terraform. No data, no app yet.
- S3 buckets: raw, processed, athena-results, glue-scripts
- IAM roles: Glue execution role, Step Functions execution role
- Glue Catalog: three databases — `bronze_db`, `silver_db`, `gold_db`
- Athena workgroup with results bucket configured
- DynamoDB table for extraction watermarks
- All in `terraform/environments/dev/` using modules from `terraform/modules/`

### Phase 2 — E-Commerce App
**Goal:** A real, working web app that generates transactional data.
- FastAPI backend with SQLAlchemy models
- Tables: `users`, `products`, `orders`, `order_items`, `payments`, `page_views`
- Features: product catalog, user registration, shopping cart, checkout, payments
- All activity writes to PostgreSQL — realistic data patterns (not random)
- Docker Compose: `app` service + `postgres` service
- App also provisions RDS via Terraform (same schema) for cloud deployment

### Phase 3 — Extraction Layer
**Goal:** Pull data from app's PostgreSQL into S3 Bronze via Glue JDBC.
- One Glue job per table (extract_orders.py, extract_customers.py, etc.)
- Watermark pattern: read last timestamp from DynamoDB → extract WHERE created_at > watermark → write CSV to Bronze S3 → update DynamoDB watermark
- Bronze S3 path: `bronze/{table}/year=YYYY/month=MM/day=DD/`
- Glue JDBC connection configured to RDS (credentials from Secrets Manager)
- Glue Crawler runs after extraction to register new partitions

### Phase 4 — ETL Layer
**Goal:** Bronze CSV → Silver Parquet via Glue PySpark jobs.
- One Glue job per table
- Operations: type casting, null handling, deduplication, column standardization
- Output: Parquet + Snappy, Hive-partitioned
- Silver path: `silver/{table}/year=YYYY/month=MM/day=DD/`
- Glue Crawler registers Silver schemas

### Phase 5 — Gold + Query Layer
**Goal:** Silver → Gold aggregations. Athena analytics queries.
- Gold jobs: daily_sales, customer_ltv, top_products, funnel_analysis
- CTAS-style Glue jobs to materialize Gold Parquet tables
- Athena queries in `athena/queries/analytics/` — validate with real bytes-scanned cost
- Partition pruning must be demonstrably working (check query execution stats)

### Phase 6 — Orchestration
**Goal:** Full automated pipeline triggered on schedule.
- Step Functions state machine: Extract → Crawl → Transform → Validate → Alert
- EventBridge rule: trigger Step Functions on schedule (e.g., hourly or daily)
- Error handling: retry on transient failures, SNS alert on terminal failure
- Pipeline idempotent: safe to re-trigger for the same time window

### Phase 7 — Monitoring
**Goal:** Know when the pipeline is unhealthy before users do.
- CloudWatch alarms: Glue job failure, Step Functions execution failure, Athena query errors
- CloudWatch dashboard: pipeline run status, data freshness lag, DPU-hours consumed
- Log groups for all Glue jobs
- SNS topic → email notification on any alarm breach

### Phase 8 — Data Quality
**Goal:** Automated quality gate — bad data stops the pipeline.
- Great Expectations suites: one per Silver table
- Checks: null rates, duplicate primary keys, value range assertions, referential integrity
- Quality check integrated into Step Functions: fail state if GE suite fails
- Quality results stored to S3 for historical tracking

### Phase 9 — Advanced (Future)
- Apache Iceberg format on Silver/Gold (time travel, upserts, schema evolution)
- AWS DMS for CDC extraction (replaces watermark JDBC pattern)
- EMR cluster for Spark at scale (replaces Glue for heavy jobs)

---

## Directory Map

```
app/
  backend/           ← FastAPI app code (zero AWS dependencies)
  frontend/          ← Jinja2 templates + static files
  docker-compose.yml ← Local dev: app + postgres

terraform/
  modules/{s3, glue, rds, athena, iam, step_functions, monitoring}/
  environments/{dev, prod}/
  global/            ← Shared provider config

pipeline/
  extraction/glue_jobs/    ← JDBC extractor jobs (one per table)
  transformation/glue_jobs/
    bronze_to_silver/      ← PySpark clean/type/dedup jobs
    silver_to_gold/        ← PySpark aggregation jobs
  quality/                 ← Great Expectations suites
  utils/                   ← Watermark helper, S3 helper, secrets

athena/queries/      ← .sql files (never hardcode S3 paths — use catalog)
orchestration/       ← Step Functions ASL JSON definition
monitoring/          ← CloudWatch JSON for dashboards + alarms
tests/unit/          ← Pure Python, no AWS
tests/integration/   ← Real AWS dev account required
tests/app/           ← FastAPI TestClient tests
docs/architecture/decisions/  ← ADRs
```

---

## Terraform Conventions

- Every module has exactly: `main.tf`, `variables.tf`, `outputs.tf`
- Environment layer (`environments/dev/`) composes modules — zero resource definitions there
- State: local (`terraform.tfstate` — gitignored, not committed)
- Naming: `datalakehouse-{env}-{resource}` (e.g. `datalakehouse-dev-raw`)
- Every resource tagged: `Project=datalakehouse`, `Environment={env}`, `ManagedBy=terraform`, `Phase={n}`
- No `count` for environments — use separate env directories
- Sensitive values (DB password, etc.) from `terraform.tfvars` — never committed, listed in `.gitignore`

---

## Glue Extraction Job Pattern

Each extraction job follows this exact pattern:

1. Read last watermark from DynamoDB
2. Open JDBC connection to RDS (credentials from Secrets Manager)
3. Execute: `SELECT * FROM {table} WHERE created_at > {watermark} AND created_at <= NOW()`
4. Write result as CSV to `s3://raw/bronze/{table}/year=YYYY/month=MM/day=DD/{job_run_id}.csv`
5. Update DynamoDB watermark to the max `created_at` from the extracted batch
6. Log row count, time range covered

Key rules:
- Watermark stored per-table in DynamoDB: `table_name` (PK), `last_extracted_at` (string ISO8601)
- Use a **closed upper bound** (`<= NOW()`) — never extract the "in-flight" current second
- Write to S3 before updating watermark (not after) — ensures re-runability on failure

---

## Glue ETL (Bronze → Silver) Pattern

Each Silver job:

1. Read all unprocessed Bronze partitions (or specific partition passed as job arg)
2. Apply per-column transformations:
   - Cast strings to proper types (timestamps, decimals, booleans)
   - Standardize nulls (empty string → null)
   - Drop exact duplicates
   - Validate primary key uniqueness
3. Write Parquet + Snappy to Silver path
4. Do NOT re-read source to verify — trust PySpark write guarantee

---

## App Database Schema (PostgreSQL)

```sql
users        (id, email, name, password_hash, created_at, updated_at)
products     (id, name, category, description, price, stock_qty, created_at)
orders       (id, user_id, status, subtotal, tax, total, created_at, updated_at)
order_items  (id, order_id, product_id, quantity, unit_price, created_at)
payments     (id, order_id, amount, method, status, transaction_ref, created_at)
page_views   (id, user_id, session_id, path, referrer, duration_ms, created_at)
```

`created_at` on every table — this is the watermark column for extraction.

---

## S3 Naming

```
datalakehouse-{env}-raw           ← Bronze layer only
datalakehouse-{env}-processed     ← Silver + Gold layers
datalakehouse-{env}-athena-results← Athena output
datalakehouse-{env}-glue-scripts  ← Glue job .py files uploaded here
```

---

## IAM Roles

| Role | Permissions |
|---|---|
| `glue-extraction-role` | RDS connect (via Glue connection), S3 write to raw bucket, DynamoDB read/write watermarks table, Secrets Manager read |
| `glue-etl-role` | S3 read raw, S3 write processed, Glue Catalog read/write |
| `step-functions-role` | Invoke Glue jobs + crawlers, SNS publish |
| `athena-query-role` | S3 read processed, S3 write athena-results, Glue Catalog read |

Never use `*` in Action unless documented with a specific reason.

---

## Partitioning Strategy

| Table | Bronze Partition | Silver Partition | Notes |
|---|---|---|---|
| orders | year/month/day | year/month/day | Daily batch |
| customers/users | year/month/day | year/month | Slower growth |
| products | year/month/day | (none — full refresh) | Small, static |
| order_items | year/month/day | year/month/day | Joined with orders |
| payments | year/month/day | year/month/day | Daily batch |
| page_views | year/month/day | year/month/day/hour | High volume |

---

## Python Conventions

- `pyproject.toml` for deps and tool config
- `ruff` for linting + formatting (not black/flake8)
- `pytest` for all tests
- Type hints required on all function signatures
- No hardcoded credentials anywhere
- App code: zero AWS imports (`boto3`, `botocore`) — app is AWS-agnostic
- Pipeline code: no business logic — only extract, transform, load

---

## What NOT To Do

- **Never** create AWS resources via console — Terraform only
- **Never** commit `terraform.tfstate`, `terraform.tfstate.backup`, `.tfvars`, `.env`, AWS credentials
- **Never** import boto3 in `app/` code — app must be AWS-agnostic
- **Never** write to Bronze from ETL jobs — Bronze is written only by extraction jobs
- **Never** modify app database from the pipeline — read-only access
- **Never** skip Glue Crawler after writing new partitions — Athena won't find them
- **Never** update watermark before confirming S3 write succeeded
- **Never** run `terraform apply` in prod without reviewing `terraform plan` first
