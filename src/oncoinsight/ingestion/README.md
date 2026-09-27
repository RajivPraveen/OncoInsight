# `ingestion/`: extracting real clinical data from public APIs

[← package overview](../README.md)

| File | Source | What is extracted |
|---|---|---|
| `gdc.py` | [NCI Genomic Data Commons](https://api.gdc.cancer.gov) `POST /cases`, project **TCGA-BRCA** | 1,098 cases with demographics, diagnoses (AJCC stage, TNM, histology), **4,948 treatments with day offsets from diagnosis**, pathology details, follow-ups, ER/PR/HER2 molecular tests and the contributing tissue source site |
| `cbioportal.py` | [cBioPortal](https://www.cbioportal.org) REST API | `brca_tcga_pan_can_atlas_2018`: curated OS / DSS / PFI / DFI endpoints (TCGA Clinical Data Resource) and PAM50 subtype. `brca_metabric`: 2,509-patient validation cohort with ~10-year follow-up |
| `http.py` | n/a | Shared `httpx` client with `tenacity` exponential backoff: retries 5xx and 429, fails fast on other 4xx |

## Behaviour

- **Pagination** at 250 cases per request, with a manifest (`_manifest.json.gz`) written next to each run.
- **Run-partitioned raw layer:** `gdc/tcga-brca/cases/run_id=<UTC timestamp>/part-0000.json.gz`. Raw data is
  immutable, so any run can be replayed.
- **Incremental mode** filters on `updated_datetime >= watermark`. The watermark lives in `ops.ingestion_watermarks`
  and only advances after a *successful* load. Because GDC doesn't always bump the case timestamp when nested
  records change, a weekly full reconciliation re-pulls everything.
- No credentials are required: both APIs serve open-access, de-identified research data.
