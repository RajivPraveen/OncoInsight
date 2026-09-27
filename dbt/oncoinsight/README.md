# `dbt/oncoinsight`: the analytics warehouse

[← back to project README](../../README.md)

A layered dbt project on PostgreSQL that turns quality-gated FHIR and registry data into a **star schema** and
**14 analysis marts**. **44 models · 5 seeds · 98 tests · 4 exposures.**

```mermaid
flowchart LR
  SRC[(raw.fhir_* · raw.cbio_*<br/>11 sources)]:::s --> STG[staging<br/>9 views]:::a --> INT[intermediate<br/>7 tables]:::b --> CORE[core star schema<br/>7 dims · 7 facts]:::c --> MARTS[marts<br/>14 analysis tables]:::d
  SEEDS[seeds<br/>CMS prices · drug catalogue<br/>stage order · site types]:::e --> INT
  MARTS --> EXP[exposures<br/>dashboard · API · Power BI · AI]:::f
  classDef s fill:#52514e,color:#fff; classDef a fill:#2a78d6,color:#fff; classDef b fill:#1baf7a,color:#fff
  classDef c fill:#eb6834,color:#fff; classDef d fill:#e87ba4,color:#000; classDef e fill:#eda100,color:#000
  classDef f fill:#4a3aa7,color:#fff
```

| Folder | Schema | Materialisation | Purpose |
|---|---|---|---|
| [`models/staging`](models/staging/) | `stg` | view | Rename, cast and filter soft-deleted rows; one model per source table |
| [`models/intermediate`](models/intermediate/) | `int` | table | Clinical business logic: index diagnosis, receptor subtype, treatment timeline, pathways, follow-up, cost lines |
| [`models/marts/core`](models/marts/core/) | `core` | table / **incremental** | Kimball star schema for BI (Power BI connects here) |
| [`models/marts/analytics`](models/marts/analytics/) | `marts` | table | Analysis-ready marts for the dashboard, API, statistics and AI assistant |
| [`seeds`](seeds/) | `ref` | seed | Versioned reference data: CMS 2026 prices, drug catalogue, costing rules, AJCC stages, site types |
| [`macros`](macros/) | n/a | n/a | Schema naming, safe casting, stage/age helpers, incremental filter, generic tests, reader grants |
| [`tests`](tests/) | n/a | n/a | Singular reconciliation tests |

## Run

```bash
dbt build --profiles-dir .
```

```bash
dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .
```

Connection settings come from environment variables (see `profiles.yml`; targets `dev` and `ci`). CI passes
`--vars '{min_patient_rows: 100, min_metabric_rows: 200}'` so row-count tests fit the fixture sample.

## Design decisions

- **Custom schema names** (`stg`, `int`, `core`, `marts`, `ref`) are used verbatim, so BI tools see stable names.
- **Incremental facts** (`fact_treatment`, `fact_medication`, `fact_observation`, `fact_encounter`) use
  `delete+insert` on `_loaded_at`. `fact_treatment` has a post-hook that removes rows soft-deleted at source.
- **No external packages:** generic tests are defined in-repo, so builds work offline and in CI.
- **Least privilege:** an `on-run-end` hook grants the read-only `onco_reader` role usage on curated schemas only.
- **Exposures** declare the dashboard, API, Power BI model and AI assistant as downstream consumers.
