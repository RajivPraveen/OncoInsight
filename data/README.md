# `data/`: local working data (git-ignored)

[← back to project README](../README.md)

Created at runtime and never committed. Contents after `make pipeline`:

| Path | Contents |
|---|---|
| `raw/gdc/tcga-brca/cases/run_id=…/` | Gzip JSON pages from the GDC API, plus a run manifest |
| `raw/cbioportal/<study>/run_id=…/` | cBioPortal clinical attributes, patient and sample records |
| `raw/fhir/tcga-brca/run_id=…/` | FHIR R4 NDJSON bulk files (one per resource type) |
| `raw/quarantine/` | Any FHIR resources that failed schema validation |
| `models/` | Trained 5-year relapse model (`.joblib`) and its metadata |
| `exports/powerbi/` | Parquet exports from `make powerbi` |

With `ONCO_STORAGE_BACKEND=s3`, the `raw/` tree lives in the S3 bucket instead.
