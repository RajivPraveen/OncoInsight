# `docs/`: project documentation

[← back to project README](../README.md)

| Document | Read it to learn |
|---|---|
| [architecture.md](architecture.md) | The data flow, warehouse schemas and access model, incremental processing, orchestration, serving layer, and the key design decisions and why they were made |
| [data_sources.md](data_sources.md) | Where every record comes from, the GDC → FHIR R4 mapping (resources, LOINC/ICD codes), and dbt lineage |
| [data_dictionary.md](data_dictionary.md) | Every table and column in the curated schemas (generated from the live warehouse) |
| [metric_definitions.md](metric_definitions.md) | Exact definitions of every KPI and metric, the cost model, the what-if levers and the alert rule |
| [assumptions_and_limitations.md](assumptions_and_limitations.md) | What the data can and can't support, and how to interpret the results responsibly |
| [runbook.md](runbook.md) | Schedules, failure handling, backfills and replays, secrets and access |
| [cost_reference_sources.md](cost_reference_sources.md) | Provenance of all 35 CMS 2026 reference prices (files, versions, conversion factor, substitutions, gaps) |
| `images/` | README charts and dashboard screenshots, regenerated with `make readme-assets` |
