# `models/`: dbt models by layer

[← dbt project](../README.md)

| Folder / file | Layer |
|---|---|
| [`staging/`](staging/) | 9 typed views over the raw FHIR and registry tables |
| [`intermediate/`](intermediate/) | 7 tables of clinical business logic (diagnosis, subtype, treatment timeline, pathways, follow-up, cost lines) |
| [`marts/core/`](marts/core/) | Star schema: 7 dimensions and 7 facts |
| [`marts/analytics/`](marts/analytics/) | 14 analysis marts |
| `exposures.yml` | Downstream consumers: dashboard, REST API, Power BI model, AI assistant |
