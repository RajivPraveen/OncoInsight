# Power BI kit

Power BI Desktop is Windows-only, so no `.pbix` is committed. This folder contains everything needed to build
the report on the modelled warehouse in about 30 minutes: connection steps, the star schema, relationships, DAX
measures ([measures.dax](measures.dax)) and a theme ([oncoinsight_theme.json](oncoinsight_theme.json)) that uses
the same validated colour palette as the Streamlit dashboard.

## 1. Connect (DirectQuery or Import)

1. **Get Data → PostgreSQL database**. Server `localhost:5433` (docker) or the RDS endpoint (Terraform output
   `warehouse_endpoint`); database `oncoinsight`.
2. Sign in with the read-only role `onco_reader`. It can read only `core`, `marts`, `ref`, `analytics` and `ops`.
3. Select the tables below. Use **Import** for the dashboard (the data refreshes daily) or **DirectQuery** for
   always-current KPI pages.
4. The PostgreSQL connector needs the Npgsql provider (bundled in current Power BI Desktop). For the Power BI
   Service, use an on-premises data gateway, or put a gateway VM inside the VPC for RDS.

Offline alternative: `uv run python scripts/export_powerbi.py` writes every table below as Parquet to
`data/exports/powerbi/` (Get Data → Parquet).

## 2. Model (star schema)

| Table | Role | Key |
|---|---|---|
| `core.fact_treatment` | fact (grain: treatment record) | `treatment_id` |
| `core.fact_estimated_cost` | fact (grain: cost line) | `cost_line_id` |
| `core.fact_diagnosis` | fact (grain: patient's index diagnosis) | `diagnosis_id` |
| `core.fact_encounter` | fact (grain: follow-up visit) | `encounter_id` |
| `core.fact_outcome` | fact (grain: patient) | `patient_id` |
| `core.dim_patient` | dimension | `patient_id` |
| `core.dim_hospital` | dimension | `hospital_id` |
| `core.dim_stage` | dimension | `stage_group` |
| `core.dim_biomarker` | dimension | `biomarker_key` |
| `core.dim_cancer` | dimension | `cancer_key` |
| `core.dim_treatment` | dimension | `treatment_key` |
| `marts.mart_patient_360` | wide analysis table (for patient-level pages) | `patient_id` |
| `marts.mart_kpi_annual`, `marts.mart_pathway_transitions`, `analytics.km_curves`, `ops.kpi_alerts` | report-specific tables | n/a |

**Relationships** (single direction, many-to-one, dimension → fact):

```
dim_patient[patient_id]      1 ─► * fact_treatment[patient_id], fact_diagnosis[patient_id], fact_encounter[patient_id],
                                    fact_outcome[patient_id] (1:1), fact_estimated_cost[patient_id]
dim_hospital[hospital_id]    1 ─► * fact_treatment[hospital_id], fact_diagnosis[hospital_id]
dim_stage[stage_group]       1 ─► * fact_diagnosis[stage_group]
dim_biomarker[biomarker_key] 1 ─► * fact_diagnosis[biomarker_key]
dim_cancer[cancer_key]       1 ─► * fact_diagnosis[cancer_key]
dim_treatment[treatment_key] 1 ─► * fact_treatment[treatment_key]
fact_treatment[treatment_id] 1 ─► * fact_estimated_cost[treatment_id]
```

Sort `dim_stage[stage_group]` by `stage_order`, and `dim_patient[age_group]` with a small sort table
(`<40`, `40-49`, `50-64`, `65-74`, `75+`).

## 3. Report pages (suggested)

1. **Executive overview**: cards (patients, median days to chemo, % > 90 days, crude recurrence, mean estimated
   cost), diagnoses by year, latest high alerts (`ops.kpi_alerts`).
2. **Operations**: KPI trend by site (`mart_kpi_annual`) with a site slicer. Modality volumes.
3. **Time to treatment**: site medians vs network median (`mart_delay_by_hospital`). O/E chart from
   `analytics.hospital_risk_adjusted_delay`.
4. **Treatment pathways**: Sankey custom visual (e.g. "Sankey Chart" by Microsoft from AppSource) on
   `mart_pathway_transitions[source, target, n_patients]`. Pathway table from `mart_treatment_pathways`.
5. **Survival**: line chart of `analytics.km_curves` (x = `time_months`, y = `survival`, legend = `group_value`),
   filtered by cohort / endpoint / stratifier slicers.
6. **Cost**: stacked bars by pathway and component (`fact_estimated_cost[cost_component]`).
7. **Equity**: matrix from `mart_disparities` with the n ≥ 11 filter applied.

Apply the theme via **View → Themes → Browse for themes → oncoinsight_theme.json**.
