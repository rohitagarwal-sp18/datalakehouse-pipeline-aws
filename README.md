# Enterprise Data Lakehouse Pipeline on AWS

A production-grade, medallion-architecture data lakehouse on AWS. A real standalone e-commerce app generates live transactional data — the pipeline extracts, transforms, and serves it as analytics-ready tables.

> **Status:** Phase 8 — Data Quality (Complete) · Phase 9 (Not Started)

---

## The Core Idea

```
Real App (runs standalone)  →  Pipeline extracts from it  →  Analytics layer
```

Two completely decoupled systems:

1. **E-commerce App** — a real web app with users, products, orders, payments. Runs independently. Has no knowledge of the data pipeline. Writes only to its own PostgreSQL database.

2. **Data Pipeline** — an AWS-native batch pipeline that periodically reaches into the app's database, extracts what's new, transforms it through three layers (Bronze → Silver → Gold), and makes it queryable via Athena.

This mirrors exactly how real companies operate: the source system team and the data engineering team are separate. The pipeline is non-invasive.

---

## Architecture

```mermaid
flowchart TD
    subgraph APP["E-Commerce App (Standalone)"]
        Browser["🌐 Browser"]
        API["FastAPI Backend"]
        PG[("PostgreSQL\nusers · products · orders\norder_items · payments · page_views")]
        Browser --> API --> PG
    end

    subgraph EXTRACT["Extraction Layer"]
        GLUE_EXT["AWS Glue\nJDBC Extraction Job\n(watermark-based, incremental)"]
        DDB[("DynamoDB\nWatermarks\nlast_extracted_at per table")]
        GLUE_EXT <-->|read / update watermark| DDB
    end

    subgraph BRONZE["Bronze Layer — Raw Zone"]
        S3B["S3: datalakehouse-{env}-raw\nbronze/{table}/year=../month=../day=../\nFormat: CSV  ·  immutable  ·  append-only"]
        CRAWLER_B["Glue Crawler\n(registers schema → Glue Catalog)"]
        S3B --> CRAWLER_B
    end

    subgraph SILVER["Silver Layer — Cleaned"]
        GLUE_S["AWS Glue ETL Job\nPySpark: type-cast · dedup · null-handle"]
        S3S["S3: datalakehouse-{env}-processed\nsilver/{table}/year=../month=../day=../\nFormat: Parquet + Snappy"]
        CRAWLER_S["Glue Crawler"]
        GLUE_S --> S3S --> CRAWLER_S
    end

    subgraph GOLD["Gold Layer — Analytics-Ready"]
        GLUE_G["AWS Glue ETL Job\nPySpark: aggregations"]
        S3G["S3: datalakehouse-{env}-processed\ngold/daily_sales · customer_ltv · top_products · funnel"]
        GLUE_G --> S3G
    end

    subgraph CATALOG["Glue Data Catalog"]
        DB_B["bronze_db"]
        DB_S["silver_db"]
        DB_G["gold_db"]
    end

    subgraph QUERY["Query & Observability"]
        ATHENA["Amazon Athena\nServerless SQL"]
        CW["CloudWatch\nAlarms · Dashboard · Logs"]
    end

    subgraph ORCH["Orchestration"]
        SF["AWS Step Functions\nExtract → Crawl → Transform → Validate → Notify"]
        EB["EventBridge\nScheduled Trigger"]
        EB --> SF
    end

    PG -->|JDBC read-only| GLUE_EXT
    GLUE_EXT -->|write CSV| S3B
    CRAWLER_B -->|register| DB_B
    DB_B -->|read| GLUE_S
    CRAWLER_S -->|register| DB_S
    DB_S -->|read| GLUE_G
    GLUE_G -->|register| DB_G
    DB_G -->|query| ATHENA
    SF -->|orchestrates| GLUE_EXT
    SF -->|orchestrates| GLUE_S
    SF -->|orchestrates| GLUE_G
    S3B & S3S & S3G -->|logs + metrics| CW
```

---

## Tech Stack

### E-Commerce App

| Layer | Technology |
|---|---|
| Backend | Python + FastAPI |
| Database | PostgreSQL 15 (Docker locally, RDS in cloud) |
| Frontend | HTML + Vanilla JS (Jinja2 templates) |
| Container | Docker + Docker Compose |

### Data Pipeline (AWS)

| Layer | Technology |
|---|---|
| Cloud | AWS |
| Infrastructure as Code | Terraform >= 1.6 |
| Extraction | AWS Glue (JDBC → S3) |
| ETL / Processing | AWS Glue + PySpark |
| Orchestration | AWS Step Functions |
| Storage | Amazon S3 |
| Metadata Catalog | AWS Glue Data Catalog |
| Querying | Amazon Athena v3 |
| App Database | Amazon RDS PostgreSQL |
| Monitoring | CloudWatch |
| Secrets | AWS Secrets Manager |
| Data Quality | Great Expectations |
| Data Format | CSV (Bronze), Parquet/Snappy (Silver + Gold) |
| CI/CD | GitHub Actions |

---

## Project Structure

```
datalakehouse-pipeline-aws/
│
├── app/                                # Standalone e-commerce application (Phase 2 ✅)
│   ├── backend/
│   │   ├── main.py                     # FastAPI entrypoint + lifespan (DB init, seed)
│   │   ├── database.py                 # SQLAlchemy engine + session factory
│   │   ├── models.py                   # ORM models: User, Product, Order, OrderItem, Payment, PageView
│   │   ├── auth.py                     # JWT helpers: hash, verify, create token, get_current_user
│   │   ├── config.py                   # Env-var config (DATABASE_URL, SECRET_KEY)
│   │   ├── seed.py                     # Product seed data (runs once on startup)
│   │   ├── routes/
│   │   │   ├── auth.py                 # /login, /register, /logout
│   │   │   ├── products.py             # /, /products/{id} — with page view logging
│   │   │   ├── cart.py                 # /cart, /cart/add, /cart/update, /cart/remove
│   │   │   └── orders.py              # /checkout, /orders, /orders/{id}
│   │   └── requirements.txt
│   ├── frontend/
│   │   ├── templates/                  # Jinja2 HTML: base, index, product, cart,
│   │   │   │                           #   checkout, orders, order_detail, login, register
│   │   └── static/css/style.css
│   ├── .env.example                    # Copy to .env before docker-compose up
│   ├── docker-compose.yml              # app + postgres services
│   └── Dockerfile
│
├── terraform/                          # AWS infrastructure (Phase 1 ✅)
│   ├── modules/
│   │   ├── s3/                         # Raw, processed, athena-results, glue-scripts buckets
│   │   ├── glue/                       # Glue catalog DBs, crawlers, jobs (phase-gated)
│   │   ├── rds/                        # RDS PostgreSQL — same schema as app (Phase 2)
│   │   ├── athena/                     # Athena workgroup + 1 GB scan limit
│   │   ├── iam/                        # Glue extraction/ETL roles, Step Functions role
│   │   ├── dynamodb/                   # Watermarks table (last_extracted_at per table)
│   │   ├── networking/                 # VPC, subnets, security groups for RDS + Glue
│   │   ├── step_functions/             # State machine skeleton (Phase 6)
│   │   └── monitoring/                 # CloudWatch alarms + SNS (Phase 7)
│   ├── main.tf                         # Wires all modules (phase-gated comments)
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   └── terraform.tfvars.example
│
│   # ── Future phases ────────────────────────────────────────────────────────
│
├── pipeline/                           # Glue job source code (Phase 3+)
│   ├── extraction/glue_jobs/           # extract_{table}.py — watermark JDBC → Bronze S3
│   ├── transformation/glue_jobs/
│   │   ├── bronze_to_silver/           # PySpark: type-cast, dedup, null-handle
│   │   └── silver_to_gold/             # PySpark: daily_sales, customer_ltv, top_products
│   ├── quality/                        # Great Expectations suites (Phase 8)
│   └── utils/                          # Watermark helper, S3 helper, Secrets helper
│
├── athena/queries/                     # Analytics + validation SQL (Phase 5)
├── orchestration/step_functions/       # ASL pipeline definition JSON (Phase 6)
├── monitoring/                         # CloudWatch dashboard + alarm JSON (Phase 7)
├── tests/
│   ├── unit/                           # Transform unit tests (no AWS)
│   ├── integration/                    # Real AWS dev account required
│   └── app/                            # FastAPI TestClient tests
│
├── pyproject.toml                      # ruff + pytest config
├── .gitignore
├── CLAUDE.md
└── README.md
```

---

## Build Phases

| Phase | Name | What Gets Built | Status |
|---|---|---|---|
| 1 | Foundation | S3 buckets, IAM roles, Glue Catalog, Athena workgroup — all via Terraform (local state) | ✅ Complete |
| 2 | E-Commerce App | FastAPI app + PostgreSQL + Docker Compose. Users, products, orders, payments, page views. | ✅ Complete |
| 3 | Extraction Layer | Glue JDBC jobs: extract from RDS → write CSV to Bronze S3 with watermarking | ✅ Complete |
| 4 | ETL Layer | Glue PySpark jobs: Bronze CSV → Silver Parquet (typed, deduplicated, partitioned) | ✅ Complete |
| 5 | Gold + Query Layer | Silver aggregations → Gold tables. Athena SQL analytics queries. | ✅ Complete |
| 6 | Orchestration | Step Functions: schedule and chain Extract → Crawl → Transform → Validate | ✅ Complete |
| 7 | Monitoring | CloudWatch alarms for Glue failures, Athena costs, pipeline SLA | ✅ Complete |
| 8 | Data Quality | Great Expectations checks as pipeline gate — fail pipeline if data quality drops | ✅ Complete |
---

## Data Model

### App Database (PostgreSQL)

| Table | Key Columns | Extracted How |
|---|---|---|
| `users` | id, email, name, created_at | Full + incremental on `created_at` |
| `products` | id, name, category, price, stock | Full (small, slowly changing) |
| `orders` | id, user_id, status, total, created_at | Incremental on `created_at` |
| `order_items` | id, order_id, product_id, qty, price | Incremental on `order_id` |
| `payments` | id, order_id, amount, method, status, created_at | Incremental on `created_at` |
| `page_views` | id, user_id, path, referrer, created_at | Incremental on `created_at` |

### Extraction Pattern: Watermarking

Each Glue extraction job tracks a **watermark** — the last extracted `created_at` timestamp, stored in DynamoDB or S3. On each run:

```
SELECT * FROM orders WHERE created_at > {last_watermark} ORDER BY created_at
```

This ensures: no full table scans, no duplicates, idempotent re-runs.

### Gold Layer Aggregations

| Table | Description | Source |
|---|---|---|
| `daily_sales` | Revenue, order count, AOV per day | orders + payments |
| `customer_ltv` | Lifetime value and order frequency per user | users + orders + payments |
| `top_products` | Revenue + units sold per product | order_items + products |
| `funnel_analysis` | Browse → add-to-cart → purchase conversion | page_views + orders |

---

## S3 Layout

```
s3://datalakehouse-{env}-raw/
  bronze/
    orders/year=2026/month=06/day=08/batch_id=abc123.csv
    customers/year=2026/month=06/day=08/batch_id=abc123.csv
    payments/year=2026/month=06/day=08/batch_id=abc123.csv
    order_items/year=2026/month=06/day=08/
    page_views/year=2026/month=06/day=08/hour=14/

s3://datalakehouse-{env}-processed/
  silver/
    orders/year=2026/month=06/day=08/       ← Parquet
    customers/year=2026/month=06/
    payments/year=2026/month=06/day=08/
    order_items/year=2026/month=06/day=08/
    page_views/year=2026/month=06/day=08/hour=14/
  gold/
    daily_sales/
    customer_ltv/
    top_products/
    funnel_analysis/

s3://datalakehouse-{env}-athena-results/
s3://datalakehouse-{env}-glue-scripts/
```

---

## How the Two Systems Connect

The app and pipeline are **fully decoupled**. The connection point is the RDS database:

```
App writes → PostgreSQL (RDS)
                   ↑
Pipeline reads from here (read-only connection, separate IAM role, read replica in prod)
```

The app never knows the pipeline exists. The pipeline never modifies app data. This separation is the real-world pattern.

---

## Getting Started

### Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.6
- Python >= 3.11
- Docker + Docker Compose
- `make` installed

### Run the App Locally

```bash
cd app
cp .env.example .env          # defaults work as-is for local dev
docker-compose up
# App:      http://localhost:8000
# Postgres: localhost:5432
```

On first start the app creates all tables and seeds 20 products automatically.

### Deploy Pipeline Infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Fill in: alert_email, db_password
terraform init
terraform plan
terraform apply
```

### Upload Glue Scripts to S3

After `terraform apply`, upload all pipeline scripts to the Glue scripts bucket:

```bash
BUCKET=$(terraform output -raw glue_scripts_bucket_name)

# Glue job scripts
aws s3 sync ../pipeline/extraction/glue_jobs/        s3://$BUCKET/jobs/
aws s3 sync ../pipeline/transformation/glue_jobs/bronze_to_silver/ s3://$BUCKET/jobs/
aws s3 sync ../pipeline/transformation/glue_jobs/silver_to_gold/   s3://$BUCKET/jobs/
aws s3 cp  ../pipeline/quality/run_checks.py         s3://$BUCKET/jobs/
aws s3 sync ../pipeline/quality/suites/              s3://$BUCKET/jobs/suites/

# Shared utility libs (referenced by --extra-py-files in extraction jobs)
aws s3 cp ../pipeline/utils/watermark.py      s3://$BUCKET/libs/watermark.py
aws s3 cp ../pipeline/utils/secrets_helper.py s3://$BUCKET/libs/secrets_helper.py

# PostgreSQL JDBC driver (required by Glue extraction jobs)
curl -o postgresql-42.7.0.jar https://jdbc.postgresql.org/download/postgresql-42.7.0.jar
aws s3 cp postgresql-42.7.0.jar s3://$BUCKET/jars/postgresql-42.7.0.jar
```

---

## Key Concepts

### Why Watermarking Over Full Extract?
Full table extract is simple but doesn't scale. 1M orders today = full re-scan every pipeline run. Watermarking extracts only new rows — cost and time grow with daily volume, not total history.

### Why JDBC Extraction Over DMS?
AWS DMS (Change Data Capture) is more real-time but adds operational complexity. JDBC batch extraction via Glue is simpler, cheaper, and perfectly adequate for batch analytics use cases. DMS is Phase 9.

### Why Separate Bronze From Silver?
Bronze preserves the source record exactly as it arrived. If a transform has a bug, you fix the job and re-process Bronze — you never need to re-extract from the source. Bronze = replayability.

### Why Parquet in Silver?
Parquet is columnar. A query selecting 3 columns from a 50-column table scans only those 3 columns. Combined with Snappy compression, Athena query costs drop 5–10x compared to CSV.

---

## Cost Targets (Dev)

| Resource | Expected Monthly Cost |
|---|---|
| RDS db.t3.micro (app DB) | ~$15 |
| S3 storage (dev volume) | < $1 |
| Glue jobs (per run) | ~$0.10 per run |
| Athena (per query) | < $0.01 per query |
| Step Functions | Free tier |
| **Total (light usage)** | **~$20/month** |
