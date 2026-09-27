# `models/marts/analytics`: analysis-ready marts

[← dbt project](../../../README.md)

Consumed by the dashboard, REST API, statistics modules and AI assistant (declared as dbt exposures).

| Mart | Grain | Answers |
|---|---|---|
| `mart_patient_360` | patient | The single wide view: demographics, site, diagnosis, subtype, pathway, day offsets to each modality, chemo-timing group, follow-up, curated outcomes and cost components |
| `mart_treatment_pathways` | pathway | How common is each sequence, how long it takes, what it costs, crude outcomes (pathways with n < 10 grouped) |
| `mart_pathway_transitions` | step → step edge | Aggregated Sankey edges from diagnosis to outcome |
| `mart_patient_pathway_steps` | patient × step | Patient-level steps with cohort attributes, so journeys can be re-aggregated for any filter |
| `mart_treatment_delay` | patient × interval | Diagnosis → chemo / radiation / endocrine / first adjuvant, and chemo end → radiation, with stratifiers |
| `mart_delay_by_hospital` | site × interval | Median / IQR / p90, share over 90 days, difference vs network (benchmarkable sites only) |
| `mart_survival` | patient | Survival analysis set with covariates (feeds lifelines) |
| `mart_recurrence` / `mart_recurrence_summary` | patient / factor | Progression analysis set and crude rates by stage, subtype, pathway, age, T and N |
| `mart_cost_analysis` | dimension value | Estimated cost by pathway, stage, subtype and site type, with component shares |
| `mart_kpi_annual` | entity × diagnosis year | Operational KPIs for the network and each site (feeds the KPI monitor) |
| `mart_disparities` | group | Equity metrics: timing, guideline-concordant treatment, outcomes by race, ethnicity, age, site type, country |
| `mart_treatment_adherence` | treatment record | Cycles vs standard regimen, endocrine duration, reported treatment outcome |
| `mart_metabric_cohort` | patient | Cleaned METABRIC validation cohort with receptor subtype and treatment combination |

`_marts.yml` documents the key columns and tests uniqueness, ranges, accepted values and row counts.
