# `quality/`: the pre-load data-quality gate

[← package overview](../README.md)

`expectations.py` defines Great Expectations (GX Core 1.x) suites for every raw table. **72 expectations** in total.
Every batch is validated *before* anything is written to the warehouse.

| Severity | Examples | Effect |
|---|---|---|
| **critical** | primary key not null and unique, required foreign keys present, FHIR `status` value sets, treatment-modality domain, TCGA barcode format `TCGA-XX-XXXX`, required registry columns exist | Raises `DataQualityError`; the run is logged as `failed_dq` and **nothing is loaded** |
| **warning** | age 18–90, days-to-death range, treatment end ≥ start, radiation fractions 1–60, year of diagnosis 1970–2030, table row counts | Recorded in `ops.dq_results` and shown on the dashboard's Data Quality page; the load continues |

Warnings surface genuine source quirks (for example radiation courses reported with more than 60 fractions). They are
kept and flagged, not deleted.

Cross-table checks (referential integrity, reconciliation) run after loading as dbt tests. See
[`dbt/oncoinsight`](../../../dbt/oncoinsight/).
