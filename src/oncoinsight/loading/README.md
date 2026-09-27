# `loading/`: idempotent, incremental warehouse loads

[← package overview](../README.md)

| File | What it does |
|---|---|
| `warehouse.py` | `upsert_frame()`: streams a Polars frame through `COPY` into a temp table, then `INSERT … ON CONFLICT (id) DO UPDATE` **only where the `record_hash` changed**. `_loaded_at` is bumped only for changed rows, which is what dbt's incremental models key on. Full-refresh loads soft-delete rows that disappeared from the source (`_is_deleted`). New source columns are added automatically (schema evolution). |
| `cbioportal_transform.py` | Pivots cBioPortal's long format (one row per patient × attribute) into one wide row per patient or sample with Polars, and adds a hash and run id. |

**Result:** re-running the pipeline on unchanged data rewrites **0 rows**, and every raw row can be traced back to
its extraction run (`source_run_id`).
