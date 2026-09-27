# `tests/fixtures/`: real-data test sample

[← tests](../README.md)

A small, **deterministic sample of the real public data** (not synthetic), regenerated with
`uv run python scripts/make_fixtures.py`:

| File | Contents |
|---|---|
| `gdc_cases.json.gz` | 150 TCGA-BRCA cases from the latest full GDC extract (hash-selected, so the sample is stable) |
| `cbio_brca_tcga_pan_can_atlas_2018_{patient,sample}.json.gz` | Matching PanCancer Atlas rows for those patients |
| `cbio_brca_metabric_{patient,sample}.json.gz` | 300 METABRIC patients |

`scripts/load_fixtures.py` stages these into the raw store as if they were an extraction run. CI uses them to run
the **entire pipeline offline** (FHIR → quality gate → load → dbt build → analytics → alerts → API tests) against a
fresh Postgres.
