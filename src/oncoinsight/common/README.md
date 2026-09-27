# `common/`: configuration, storage, database and logging

[← package overview](../README.md)

Small, dependency-light utilities that every other module builds on.

| File | What it does |
|---|---|
| `config.py` | Typed settings via `pydantic-settings`, read only from environment variables or `.env` (nothing secret is hard-coded). Covers the warehouse (owner and **read-only reader** credentials), raw-store backend (local / S3), source API URLs, KPI alert thresholds, optional API key and LLM settings. |
| `storage.py` | A single `RawStore` interface with two backends: `LocalRawStore` (atomic writes, path-traversal protection) and `S3RawStore` (SeaweedFS locally, AWS S3 in the cloud; encryption comes from the bucket's default SSE-KMS). Includes gzip JSON / NDJSON helpers. |
| `db.py` | SQLAlchemy/psycopg connections (owner or read-only), `read_sql` with Postgres `NUMERIC → float` coercion, atomic `write_frame` for analytics outputs, and the `ops` schema: pipeline run log, ingestion watermarks, data-quality results and KPI alerts. |
| `logging.py` | `structlog` JSON logs (console-pretty in a TTY), so every pipeline event is machine-searchable in Dagster, Docker or CloudWatch. |

**Design note:** API, dashboard and assistant connect with the `onco_reader` role, which is read-only, has a 30 s
statement timeout and can only see curated schemas. Only the loader and dbt use the owner role.
