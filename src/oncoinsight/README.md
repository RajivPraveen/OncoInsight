# `oncoinsight`: the platform's Python package

[← back to project README](../../README.md)

Everything that moves, validates, models, analyses and serves the data lives in this package. It is imported by the
CLI (`python -m oncoinsight.pipeline`), the Dagster assets, the FastAPI service and the Streamlit dashboard, so one
implementation backs every entry point.

## How data flows through the modules

```mermaid
flowchart LR
  ING[ingestion/<br/>GDC + cBioPortal APIs]:::a --> RAW[(raw JSON<br/>S3 / local)]:::s
  RAW --> FHIR[fhir/<br/>map · validate · flatten]:::b
  FHIR --> QA[quality/<br/>Great Expectations gate]:::c
  QA --> LOAD[loading/<br/>hash-based upserts]:::d
  LOAD --> DBT[(dbt warehouse<br/>../../dbt)]:::s
  DBT --> AN[analytics/<br/>survival · ML · equity · cost]:::e
  DBT --> MON[monitoring/<br/>KPI alerts]:::e
  DBT --> AS[assistant/<br/>semantic layer + LLM]:::f
  AN & MON & AS --> API[api/<br/>FastAPI]:::f
  classDef a fill:#4a3aa7,color:#fff; classDef b fill:#2a78d6,color:#fff; classDef c fill:#0ca30c,color:#fff
  classDef d fill:#eb6834,color:#fff; classDef e fill:#1baf7a,color:#fff; classDef f fill:#e87ba4,color:#000
  classDef s fill:#52514e,color:#fff
```

| Module | Responsibility | Key output |
|---|---|---|
| [`common/`](common/) | Settings, warehouse connections, raw-store abstraction, structured logging | shared by all modules |
| [`ingestion/`](ingestion/) | Pull TCGA-BRCA cases (GDC) and curated registry data (cBioPortal) with retries and watermarks | run-partitioned gzip JSON in the raw store |
| [`fhir/`](fhir/) | Convert GDC cases into validated FHIR R4 resources and flatten them with Polars | FHIR NDJSON bulk files, typed frames |
| [`quality/`](quality/) | Great Expectations suites that must pass *before* data is loaded | `ops.dq_results`, blocked loads on critical failures |
| [`loading/`](loading/) | Idempotent, incremental upserts into Postgres `raw.*` | `raw.fhir_*`, `raw.cbio_*` |
| [`analytics/`](analytics/) | Kaplan-Meier, Cox, RMST, recurrence ML, disparities, O/E benchmarking, cost scenarios | `analytics.*` tables |
| [`monitoring/`](monitoring/) | KPI anomaly detection against trailing baselines | `ops.kpi_alerts` (+ webhook) |
| [`assistant/`](assistant/) | Governed semantic layer, SQL guard and the tool-using LLM agent | audited answers |
| [`api/`](api/) | Read-only REST API over marts and analytics | `http://localhost:8010/docs` |
| [`pipeline.py`](pipeline.py) | CLI and orchestration-agnostic step functions | `python -m oncoinsight.pipeline all` |

## Run the pipeline

```bash
uv run python -m oncoinsight.pipeline all
```

Steps can also run one at a time: `extract`, `fhir`, `load`, `dbt`, `analytics`, `monitor`. Add `--mode incremental`
for a watermark-based refresh, or `--skip-extract` to rebuild from data already in the raw store.
