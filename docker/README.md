# `docker/`: container images and service configuration

[← back to project README](../README.md)

Start the full stack:

```bash
make stack
```

| Service (docker-compose.yml) | Host port | Notes |
|---|---|---|
| `postgres` (16-alpine) | 5433 | Warehouse. [`postgres/init/01_roles.sh`](postgres/init/01_roles.sh) creates the Dagster database, the curated schemas and the **read-only `onco_reader` role** (read-only transactions, 30 s statement timeout, default privileges on curated schemas only) |
| `s3` (SeaweedFS) | 9010 | S3-compatible raw layer ([`seaweedfs/s3.json`](seaweedfs/s3.json) holds local-only dev credentials). MinIO no longer publishes public images; in AWS this is a Terraform-managed S3 bucket |
| `dagster-webserver` / `dagster-daemon` | 3001 | Orchestration UI and scheduler, with run storage in Postgres ([`dagster/dagster.yaml`](dagster/dagster.yaml), [`dagster/workspace.yaml`](dagster/workspace.yaml)) |
| `api` | 8010 | FastAPI (`/docs`), with a health check |
| `dashboard` | 8502 | Streamlit dashboard |

**[`Dockerfile`](Dockerfile):** one image for every Python service. Python 3.11-slim, `uv sync --frozen --no-dev`,
OpenMP runtime for XGBoost, dbt manifest pre-built at build time (so Dagster loads without a warehouse), non-root
user. A shared `appdata` volume passes the trained model from the pipeline to the API and dashboard.
