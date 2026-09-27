# `models/marts/core`: star schema

[← dbt project](../../../README.md)

A Kimball-style dimensional model for BI tools (the [Power BI kit](../../../../../powerbi/) connects here).

| Dimensions | Grain |
|---|---|
| `dim_patient` | patient (age group, race/ethnicity, vital status, site) |
| `dim_hospital` | tissue source site (site type, volume tier, `is_benchmarkable`) |
| `dim_stage` | AJCC stage group (ordered, with stage category) |
| `dim_cancer` | histology / ICD-10 combination |
| `dim_biomarker` | ER / PR / HER2 combination → receptor subtype |
| `dim_treatment` | normalised agent or procedure (drug class, pathway modality, priced flag) |
| `dim_date` | calendar day 1985–2035 |

| Facts | Grain | Materialisation |
|---|---|---|
| `fact_diagnosis` | patient's index diagnosis | table |
| `fact_treatment` | treatment record (with estimated cost) | **incremental** + soft-delete post-hook |
| `fact_medication` | systemic therapy record | **incremental** |
| `fact_observation` | clinical observation ("lab result") | **incremental** |
| `fact_encounter` | follow-up visit | **incremental** |
| `fact_estimated_cost` | reference-priced cost line (the "claims" equivalent) | table |
| `fact_outcome` | patient outcome (curated OS/DSS/PFI/DFI, recurrence) | table |

`_core.yml` documents every model and adds uniqueness, not-null, accepted-values and **relationship tests** from every
fact to its dimensions.
