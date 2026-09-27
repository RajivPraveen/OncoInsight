# Architecture & design decisions

## Data flow

1. **Extract** (`oncoinsight.ingestion`). Paginated pulls from the GDC `/cases` endpoint (with `demographic`,
   `diagnoses.treatments`, `pathology_details`, `follow_ups.molecular_tests` and `tissue_source_site` expansions) and
   the cBioPortal `clinical-data` endpoints. httpx + tenacity exponential backoff: 5xx/429 are retried, other
   4xx fail fast. Each run is written as gzip JSON under a run-partitioned key
   (`gdc/tcga-brca/cases/run_id=.../part-0000.json.gz`) with a `_manifest`.
2. **Interoperability** (`oncoinsight.fhir`). Each GDC case is mapped to FHIR R4 resources (Patient, Organization,
   Condition, Observation, Procedure, MedicationAdministration, MedicationStatement, Encounter), following mCODE
   patterns and LOINC codes. Every resource is validated against the R4B schema (`fhir.resources`). Invalid
   resources are quarantined to `quarantine/…`, never silently dropped. Output is FHIR Bulk-Data-style NDJSON,
   one file per resource type. The warehouse ingests *only* FHIR for the clinical feed, as it would from an EHR
   bulk export. The registry feeds (cBioPortal) arrive as tabular extracts, like a tumour-registry file.
3. **Load** (`oncoinsight.loading`). Polars flattens FHIR (and pivots cBioPortal long→wide). The **Great Expectations
   gate** runs before anything is written. Critical expectations (keys, required fields, FHIR status value sets,
   barcode format) abort the load. Warnings (plausibility ranges, end ≥ start) are recorded in `ops.dq_results`.
   Rows are COPY'd into a temp table and upserted on `id`. A row is rewritten, and its `_loaded_at` bumped, only
   when its SHA-256 `record_hash` changes. Full-refresh runs soft-delete rows that vanished from the source.
4. **Transform** (dbt, `dbt/oncoinsight`). `stg` views (rename, cast, filter soft-deletes) → `int` tables
   (index diagnosis, ASCO/CAP-style receptor resolution, unified treatment timeline, pathway sequencing, follow-up,
   reference-priced cost lines) → `core` star schema (dims + incremental facts) → `marts` for BI/API/ML.
5. **Analyse** (`oncoinsight.analytics`). Python reads the marts and writes result tables to `analytics.*`
   (KM curves, Cox coefficients, PH diagnostics, model metrics, disparity tests, delay drivers, O/E benchmarking).
6. **Monitor** (`oncoinsight.monitoring`). KPI anomaly detection over `mart_kpi_annual` → `ops.kpi_alerts`, with an
   optional webhook.
7. **Serve**. FastAPI and Streamlit use the least-privilege `onco_reader` role. Power BI connects to `core` + `marts`.
   The AI assistant can only use governed metrics or guard-validated SQL. Consumers are declared as **dbt
   exposures**, so lineage continues past the warehouse.

## Serving layer

| Component | Highlights |
|---|---|
| Streamlit (13 pages, `app/`) | Grouped navigation (`Home.py`), a shared component library (`theme.py`), shared figure factories (`charts.py`, also used to render README images), a persistent cohort filter row that scopes every chart, click-to-drill charts, a live survival Cohort Lab, a cost what-if simulator, an animated site timeline, and an interactive lineage graph from the dbt manifest |
| FastAPI (`/docs`) | Read-only endpoints over marts/analytics, `POST /survival/compare` (live KM + RMST + log-rank for two cohorts), `POST /metrics/query` (semantic layer), `POST /predict/recurrence-risk`, optional `X-API-Key` auth (`ONCO_API_KEY`), `x-request-id` + latency access logs |
| Analytics modules used live | `analytics/cohorts.py` (cohort survival comparison), `analytics/cost_scenarios.py` (line-level re-pricing; the default scenario is exactly $0, enforced by a test) |

## Warehouse schemas

| Schema | Owner | Contents | Reader access |
|---|---|---|---|
| `raw` | loader | quality-gated FHIR + registry landing tables (JSONB resource retained) | no |
| `stg`, `int` | dbt | cleaning / business logic | no |
| `core` | dbt | star schema: `dim_*`, `fact_*` | yes |
| `marts` | dbt | analysis-ready marts | yes |
| `ref` | dbt seeds | CMS prices, agent catalog, stage ordering, site classification | yes |
| `analytics` | Python | statistical & ML outputs | yes |
| `ops` | platform | pipeline runs, watermarks, DQ results, KPI alerts | yes |

`onco_reader` is `default_transaction_read_only`, has a 30 s `statement_timeout`, and has no privileges on `raw`,
`stg` or `int`. The integration tests assert this.

## Incremental processing

- **Source**: GDC incremental mode filters `updated_datetime >= watermark` (stored in `ops.ingestion_watermarks`,
  advanced only after a successful load). GDC does not always bump the case timestamp when nested entities
  change, so a **weekly full reconciliation** job re-pulls everything and soft-deletes removed records.
- **Raw**: hash-based change detection means unchanged rows are not rewritten (a re-run changes 0 rows).
- **dbt**: `fact_treatment`, `fact_medication`, `fact_observation` and `fact_encounter` are `incremental`
  (`delete+insert` on the natural key, filtered on `_loaded_at`). `fact_treatment` has a post-hook that removes
  rows whose source records were soft-deleted.

## Orchestration (Dagster)

Software-defined assets mirror the lineage. dbt sources map onto the raw-table assets, so lineage is continuous
from the API to the dashboard. dbt tests become Dagster **asset checks** (81). Extraction assets have an
exponential `RetryPolicy`. Jobs: `daily_incremental_refresh` (06:00 UTC) and `weekly_full_reconciliation`
(Sunday 03:00 UTC, `--full-refresh`). A run-failure sensor posts to `ONCO_ALERT_WEBHOOK_URL`.

## Key design decisions

| Decision | Why |
|---|---|
| Real public cohorts instead of synthetic data | Real gaps (undated treatments, biobank sites, obfuscated ages, noisy labels) force production-grade handling |
| FHIR as the clinical interface | Mirrors how EHR data arrives (Bulk FHIR). Decouples source quirks from the warehouse |
| Anchor dates at 1 July of the diagnosis year, but compute every interval from exact day offsets | TCGA only publishes offsets + year. The anchor enables calendar views without distorting intervals |
| Great Expectations *before* load, dbt tests *after* | GX blocks bad batches from entering. dbt enforces cross-table integrity and business rules |
| Hospital benchmarking restricted to treating facilities with n ≥ 20, plus O/E case-mix adjustment | Several TCGA sites are biorepositories. Raw medians would confound case mix |
| Small-cell suppression (n < 11) in the semantic layer, API and dashboard | Standard CMS/NCHS privacy convention, even for public data |
| Semantic layer + SQL guard for the LLM | The model never writes free SQL against raw data. Every query is audited and read-only |
| XGBoost optional with HistGradientBoosting fallback | Portable on machines without an OpenMP runtime. XGBoost is used in the Linux image |
| Cox models report status/EPV instead of failing | Small subsets (CI fixtures, rare strata) must not block the pipeline. Low-EPV models are flagged |
