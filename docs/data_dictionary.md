# Data dictionary

Generated from the live warehouse (`scripts/gen_data_dictionary.py`) with dbt model descriptions. Grain and business rules for each metric are in [metric_definitions.md](metric_definitions.md).

## `core`

### `core.dim_biomarker`

Approx. rows: 23

| Column | Type | Description |
|---|---|---|
| `biomarker_key` | text |  |
| `er_status` | text |  |
| `pr_status` | text |  |
| `her2_status` | text |  |
| `hr_status` | text |  |
| `receptor_subtype` | text |  |

### `core.dim_cancer`

Approx. rows: 30

| Column | Type | Description |
|---|---|---|
| `cancer_key` | text |  |
| `morphology_code` | text |  |
| `histology_group` | text |  |
| `icd10_code` | text |  |
| `diagnosis_text` | text |  |

### `core.dim_date`

Approx. rows: 18,627

| Column | Type | Description |
|---|---|---|
| `date_day` | date |  |
| `year` | integer |  |
| `quarter` | integer |  |
| `month` | integer |  |
| `year_month` | text |  |
| `year_quarter` | text |  |
| `iso_day_of_week` | integer |  |

### `core.dim_hospital`

TCGA tissue source sites with site type and benchmarking eligibility.

Approx. rows: 40

| Column | Type | Description |
|---|---|---|
| `hospital_id` | text |  |
| `tss_code` | text |  |
| `hospital_name` | text |  |
| `site_type` | text |  |
| `is_treating_facility` | boolean |  |
| `n_patients` | bigint |  |
| `volume_tier` | text |  |
| `is_benchmarkable` | boolean |  |

### `core.dim_patient`

Patient dimension (TCGA-BRCA). Ages over 89 are obfuscated by TCGA.

Approx. rows: 1,098

| Column | Type | Description |
|---|---|---|
| `patient_id` | text | GDC case UUID (FHIR Patient.id) |
| `patient_barcode` | text |  |
| `gender` | text |  |
| `age_at_diagnosis` | bigint |  |
| `age_group` | text |  |
| `age_is_obfuscated` | boolean |  |
| `birth_year` | bigint |  |
| `race` | text |  |
| `ethnicity` | text |  |
| `race_ethnicity` | text |  |
| `country_of_residence` | text |  |
| `vital_status` | text |  |
| `hospital_id` | text |  |
| `_loaded_at` | timestamp with time zone |  |

### `core.dim_stage`

Approx. rows: 14

| Column | Type | Description |
|---|---|---|
| `stage_group` | text |  |
| `stage_major` | text |  |
| `stage_order` | integer |  |
| `stage_category` | text |  |

### `core.dim_treatment`

Approx. rows: 58

| Column | Type | Description |
|---|---|---|
| `treatment_key` | text |  |
| `treatment_name` | text |  |
| `drug_class` | text |  |
| `pathway_modality` | text |  |
| `route` | text |  |
| `is_priced` | boolean |  |
| `dosing_assumption` | text |  |

### `core.fact_diagnosis`

One index primary breast cancer diagnosis per patient.

Approx. rows: 1,097

| Column | Type | Description |
|---|---|---|
| `diagnosis_id` | text |  |
| `patient_id` | text |  |
| `hospital_id` | text |  |
| `anchored_diagnosis_date` | date |  |
| `year_of_diagnosis` | bigint |  |
| `cancer_key` | text |  |
| `biomarker_key` | text |  |
| `stage_group` | text |  |
| `stage_major` | text |  |
| `t_category` | text |  |
| `n_category` | text |  |
| `m_category` | text |  |
| `lymph_nodes_positive` | bigint |  |
| `lymph_nodes_examined` | bigint |  |
| `laterality` | text |  |
| `method_of_diagnosis` | text |  |
| `receptor_subtype` | text |  |
| `pam50_subtype` | text |  |

### `core.fact_encounter`

Approx. rows: 3,367

| Column | Type | Description |
|---|---|---|
| `encounter_id` | text |  |
| `patient_id` | text |  |
| `diagnosis_id` | text |  |
| `hospital_id` | text |  |
| `status` | text |  |
| `encounter_class` | text |  |
| `timepoint` | text |  |
| `days_from_diagnosis` | bigint |  |
| `anchored_encounter_date` | date |  |
| `_loaded_at` | timestamp with time zone |  |

### `core.fact_estimated_cost`

Reference-priced cost lines (CMS 2026 PFS / ASP / NADAC). Estimates, not claims.

Approx. rows: 9,616

| Column | Type | Description |
|---|---|---|
| `cost_line_id` | text |  |
| `treatment_id` | text |  |
| `patient_id` | text |  |
| `pathway_modality` | text |  |
| `cost_component` | text |  |
| `price_id` | text |  |
| `hcpcs_code` | text |  |
| `price_description` | text |  |
| `price_basis` | text |  |
| `units` | numeric |  |
| `unit_price_usd` | numeric |  |
| `estimated_amount_usd` | numeric |  |
| `used_default_quantity` | boolean |  |
| `quantity_basis` | text |  |
| `diagnosis_id` | text |  |
| `hospital_id` | text |  |
| `start_day` | bigint |  |

### `core.fact_medication`

Approx. rows: 2,897

| Column | Type | Description |
|---|---|---|
| `treatment_id` | text |  |
| `patient_id` | text |  |
| `fhir_resource_type` | text |  |
| `status` | text |  |
| `agent_raw` | text |  |
| `canonical_agent` | text |  |
| `drug_class` | text |  |
| `start_day` | bigint |  |
| `end_day` | bigint |  |
| `number_of_cycles` | bigint |  |
| `delivered_dose` | double precision |  |
| `delivered_dose_unit` | text |  |
| `route` | text |  |
| `treatment_intent` | text |  |
| `treatment_outcome` | text |  |
| `clinical_trial` | text |  |
| `_loaded_at` | timestamp with time zone |  |

### `core.fact_observation`

Approx. rows: 12,957

| Column | Type | Description |
|---|---|---|
| `observation_id` | text |  |
| `patient_id` | text |  |
| `diagnosis_id` | text |  |
| `encounter_id` | text |  |
| `category` | text |  |
| `observation_code` | text |  |
| `observation_name` | text |  |
| `value_text` | text |  |
| `value_integer` | bigint |  |
| `method` | text |  |
| `biomarker` | text |  |
| `days_from_diagnosis` | bigint |  |
| `anchored_effective_date` | date |  |
| `_loaded_at` | timestamp with time zone |  |

### `core.fact_outcome`

Approx. rows: 1,098

| Column | Type | Description |
|---|---|---|
| `patient_id` | text |  |
| `patient_barcode` | text |  |
| `os_months` | numeric |  |
| `os_event` | integer |  |
| `dss_months` | numeric |  |
| `dss_event` | integer |  |
| `pfs_months` | numeric |  |
| `pfs_event` | integer |  |
| `dfs_months` | numeric |  |
| `dfs_event` | integer |  |
| `endpoints_from_pancan_cdr` | boolean |  |
| `vital_status` | text |  |
| `last_contact_day` | bigint |  |
| `n_follow_up_visits` | bigint |  |
| `last_disease_status` | text |  |
| `gdc_recurrence_recorded` | boolean |  |
| `first_recurrence_day` | bigint |  |
| `recurrence_type` | text |  |
| `recurrence_site` | text |  |
| `any_progression_or_recurrence` | boolean |  |
| `new_tumor_event` | text |  |
| `cancer_status` | text |  |

### `core.fact_treatment`

Incremental fact - one row per treatment record for the index cancer (grain = FHIR resource).

Approx. rows: 4,948

| Column | Type | Description |
|---|---|---|
| `treatment_id` | text |  |
| `patient_id` | text |  |
| `diagnosis_id` | text |  |
| `hospital_id` | text |  |
| `fhir_resource_type` | text |  |
| `status` | text |  |
| `is_delivered` | boolean |  |
| `pathway_modality` | text |  |
| `pathway_group` | text |  |
| `treatment_key` | text |  |
| `treatment_name` | text |  |
| `drug_class` | text |  |
| `start_day` | bigint |  |
| `start_day_imputed` | boolean |  |
| `end_day` | bigint |  |
| `duration_days` | bigint |  |
| `treatment_intent` | text |  |
| `treatment_outcome` | text |  |
| `number_of_cycles` | bigint |  |
| `number_of_fractions` | bigint |  |
| `delivered_dose_cgy` | double precision |  |
| `margin_status` | text |  |
| `estimated_cost_usd` | numeric |  |
| `is_priced` | boolean |  |
| `_loaded_at` | timestamp with time zone |  |

## `marts`

### `marts.mart_cost_analysis`

Approx. rows: 31

| Column | Type | Description |
|---|---|---|
| `dimension` | text |  |
| `dimension_value` | text |  |
| `n_patients` | bigint |  |
| `mean_cost_usd` | numeric |  |
| `median_cost_usd` | numeric |  |
| `p25_cost_usd` | numeric |  |
| `p75_cost_usd` | numeric |  |
| `pct_drug` | numeric |  |
| `pct_administration` | numeric |  |
| `pct_radiation` | numeric |  |
| `pct_surgery` | numeric |  |
| `crude_mortality_pct` | numeric |  |
| `crude_recurrence_pct` | numeric |  |
| `pct_with_unpriced_treatment` | numeric |  |

### `marts.mart_delay_by_hospital`

Approx. rows: 54

| Column | Type | Description |
|---|---|---|
| `interval_name` | text |  |
| `hospital_id` | text |  |
| `hospital_name` | text |  |
| `site_type` | text |  |
| `n_patients` | bigint |  |
| `p25_days` | numeric |  |
| `median_days` | numeric |  |
| `p75_days` | numeric |  |
| `p90_days` | numeric |  |
| `pct_over_threshold` | numeric |  |
| `network_median_days` | numeric |  |
| `median_diff_vs_network_days` | numeric |  |
| `is_reportable` | boolean |  |

### `marts.mart_disparities`

Approx. rows: 37

| Column | Type | Description |
|---|---|---|
| `group_type` | text |  |
| `group_value` | text |  |
| `n_patients` | bigint |  |
| `mean_age` | numeric |  |
| `pct_stage_iii_iv` | numeric |  |
| `pct_triple_negative` | numeric |  |
| `median_days_to_chemotherapy` | numeric |  |
| `pct_chemo_over_90d` | numeric |  |
| `n_chemo_indicated` | bigint |  |
| `pct_chemo_when_indicated` | numeric |  |
| `pct_her2_targeted_among_her2_pos` | numeric |  |
| `pct_endocrine_among_hr_pos` | numeric |  |
| `pct_radiation` | numeric |  |
| `crude_mortality_pct` | numeric |  |
| `crude_recurrence_pct` | numeric |  |

### `marts.mart_kpi_annual`

Approx. rows: 132

| Column | Type | Description |
|---|---|---|
| `entity_type` | text |  |
| `entity` | text |  |
| `year_of_diagnosis` | bigint |  |
| `new_diagnoses` | bigint |  |
| `advanced_stage_diagnoses` | bigint |  |
| `chemotherapy_patients` | bigint |  |
| `radiation_patients` | bigint |  |
| `endocrine_patients` | bigint |  |
| `surgery_patients` | bigint |  |
| `median_days_to_chemotherapy` | numeric |  |
| `n_timed_chemotherapy` | bigint |  |
| `pct_chemo_over_90d` | numeric |  |
| `median_days_to_radiation` | numeric |  |
| `recurrence_rate_pct` | numeric |  |
| `mortality_rate_pct` | numeric |  |
| `mean_estimated_cost_usd` | numeric |  |

### `marts.mart_metabric_cohort`

Approx. rows: 2,509

| Column | Type | Description |
|---|---|---|
| `patient_id` | text |  |
| `age_at_diagnosis` | numeric |  |
| `age_group` | text |  |
| `cohort` | text |  |
| `tumor_size_mm` | numeric |  |
| `tumor_grade` | integer |  |
| `tumor_stage` | text |  |
| `lymph_nodes_positive` | integer |  |
| `nottingham_prognostic_index` | numeric |  |
| `pam50_claudin_subtype` | text |  |
| `er_status` | text |  |
| `pr_status` | text |  |
| `her2_status` | text |  |
| `receptor_subtype` | text |  |
| `menopausal_state` | text |  |
| `breast_surgery` | text |  |
| `received_chemotherapy` | boolean |  |
| `received_hormone_therapy` | boolean |  |
| `received_radiotherapy` | boolean |  |
| `treatment_combination` | text |  |
| `os_months` | numeric |  |
| `os_event` | integer |  |
| `dss_event` | integer |  |
| `rfs_months` | numeric |  |
| `rfs_event` | integer |  |
| `vital_status` | text |  |

### `marts.mart_pathway_transitions`

Sankey edges; source/target node labels with patient counts.

Approx. rows: 101

| Column | Type | Description |
|---|---|---|
| `source` | text |  |
| `target` | text |  |
| `source_step` | bigint |  |
| `n_patients` | bigint |  |

### `marts.mart_patient_360`

One row per patient: demographics, site, diagnosis, ER/PR/HER2 subtype, treatment pathway and timing (days from index diagnosis), follow-up, curated survival endpoints and estimated cost.

Approx. rows: 1,098

| Column | Type | Description |
|---|---|---|
| `patient_id` | text | GDC case UUID (FHIR Patient.id) |
| `patient_barcode` | text | TCGA participant barcode, e.g. TCGA-BH-A0B6 |
| `gender` | text |  |
| `age_at_diagnosis` | bigint | Age in years at index diagnosis (TCGA caps ages > 89) |
| `age_group` | text | <40, 40-49, 50-64, 65-74, 75+ |
| `race` | text |  |
| `ethnicity` | text |  |
| `race_ethnicity` | text | Hispanic, or race among non-Hispanic patients |
| `country_of_residence` | text |  |
| `hospital_id` | text |  |
| `hospital_name` | text | TCGA tissue source site (contributing hospital or biorepository) |
| `site_type` | text | Academic medical center / Cancer center / Community / Military / Biorepository (ref_site_classification) |
| `is_treating_facility` | boolean |  |
| `volume_tier` | text |  |
| `is_benchmarkable` | boolean | Treating facility with >= 20 patients; eligible for hospital comparisons |
| `year_of_diagnosis` | bigint | Diagnosis year (finest time grain published by TCGA) |
| `anchored_diagnosis_date` | date |  |
| `stage_group` | text | AJCC pathologic stage group |
| `stage_major` | text | AJCC major stage (0, I, II, III, IV, Unknown) |
| `stage_category` | text |  |
| `t_category` | text |  |
| `n_category` | text |  |
| `m_category` | text |  |
| `lymph_nodes_positive` | bigint | Regional lymph nodes positive (LOINC 21893-3) |
| `lymph_nodes_examined` | bigint |  |
| `histology_group` | text |  |
| `laterality` | text |  |
| `er_status` | text |  |
| `pr_status` | text |  |
| `her2_status` | text |  |
| `hr_status` | text |  |
| `receptor_subtype` | text | HR+/HER2-, HR+/HER2+, HR-/HER2+, Triple negative, Unknown (HER2 by ISH when available) |
| `pam50_subtype` | text | PAM50 intrinsic subtype from TCGA PanCancer Atlas |
| `pathway` | text | Ordered treatment modalities by first dated start, e.g. "Surgery → Chemotherapy → Radiation" |
| `n_pathway_steps` | bigint |  |
| `pathway_is_complete` | boolean | False when any delivered treatment lacks a start date (pathway may be missing steps) |
| `n_undated_delivered` | bigint |  |
| `received_surgery` | boolean |  |
| `received_chemotherapy` | boolean |  |
| `received_radiation` | boolean |  |
| `received_endocrine` | boolean |  |
| `received_her2_targeted` | boolean |  |
| `received_other_systemic` | boolean |  |
| `neoadjuvant_chemotherapy` | boolean |  |
| `n_treatment_records` | bigint |  |
| `n_distinct_agents` | bigint |  |
| `days_to_chemotherapy` | bigint | Days from index diagnosis to first chemotherapy (negative = neoadjuvant) |
| `days_to_radiation` | bigint | Days from index diagnosis to first radiation |
| `days_to_endocrine` | bigint | Days from index diagnosis to first endocrine therapy |
| `days_to_her2_targeted` | bigint |  |
| `days_to_first_adjuvant_treatment` | bigint |  |
| `chemotherapy_duration_days` | bigint |  |
| `treatment_span_days` | bigint |  |
| `chemo_timing_group` | text | Neoadjuvant / 0-30 / 31-60 / 61-90 / >90 days |
| `chemo_delayed_over_90d` | boolean | Adjuvant chemotherapy started > 90 days after diagnosis (JAMA Oncol 2016 threshold) |
| `n_follow_up_visits` | bigint | Follow-up encounters recorded |
| `follow_up_years` | numeric |  |
| `follow_up_visits_per_year` | numeric |  |
| `last_disease_status` | text |  |
| `vital_status` | text |  |
| `os_months` | numeric | Overall survival time (months), TCGA PanCancer CDR |
| `os_event` | integer | 1 = died, 0 = censored |
| `dss_months` | numeric |  |
| `dss_event` | integer |  |
| `pfs_months` | numeric | Progression-free interval time (months), TCGA PanCancer CDR |
| `pfs_event` | integer |  |
| `dfs_months` | numeric |  |
| `dfs_event` | integer |  |
| `any_progression_or_recurrence` | boolean | PFI event or GDC-recorded progression/recurrence |
| `days_to_recurrence` | bigint |  |
| `recurrence_type` | text |  |
| `total_estimated_cost_usd` | numeric | Sum of reference-priced cost lines (CMS 2026 PFS/ASP/NADAC; estimate, not charges) |
| `drug_cost_usd` | numeric |  |
| `administration_cost_usd` | numeric |  |
| `radiation_cost_usd` | numeric |  |
| `surgery_cost_usd` | numeric |  |
| `has_unpriced_treatment` | boolean | At least one delivered treatment without a retrieved reference price |

### `marts.mart_patient_pathway_steps`

One row per patient per ordered treatment step (first dated start of each modality group)

Approx. rows: 2,736

| Column | Type | Description |
|---|---|---|
| `patient_id` | text |  |
| `step_number` | bigint |  |
| `pathway_group` | text |  |
| `first_start_day` | bigint |  |
| `last_end_day` | bigint |  |
| `previous_group` | text |  |
| `days_since_previous_step` | bigint |  |
| `days_since_previous_end` | bigint |  |
| `year_of_diagnosis` | bigint |  |
| `stage_major` | text |  |
| `receptor_subtype` | text |  |
| `age_group` | text |  |
| `site_type` | text |  |
| `hospital_name` | text |  |
| `race_ethnicity` | text |  |
| `os_event` | integer |  |
| `any_progression_or_recurrence` | boolean |  |

### `marts.mart_recurrence`

Approx. rows: 1,063

| Column | Type | Description |
|---|---|---|
| `patient_id` | text |  |
| `time_to_event_months` | numeric |  |
| `recurrence_event` | integer |  |
| `dfs_months` | numeric |  |
| `dfs_event` | integer |  |
| `age_at_diagnosis` | bigint |  |
| `age_group` | text |  |
| `stage_major` | text |  |
| `t_category` | text |  |
| `n_category` | text |  |
| `lymph_nodes_positive` | bigint |  |
| `histology_group` | text |  |
| `receptor_subtype` | text |  |
| `pam50_subtype` | text |  |
| `er_status` | text |  |
| `her2_status` | text |  |
| `pathway_group` | text |  |
| `received_chemotherapy` | boolean |  |
| `received_radiation` | boolean |  |
| `received_endocrine` | boolean |  |
| `received_her2_targeted` | boolean |  |
| `chemo_delayed_over_90d` | boolean |  |
| `race_ethnicity` | text |  |
| `site_type` | text |  |
| `recurrence_type` | text |  |
| `days_to_recurrence` | bigint |  |
| `n_follow_up_visits` | bigint |  |
| `follow_up_visits_per_year` | numeric |  |

### `marts.mart_recurrence_summary`

Approx. rows: 36

| Column | Type | Description |
|---|---|---|
| `factor` | text |  |
| `factor_value` | text |  |
| `n_patients` | bigint |  |
| `n_recurrences` | bigint |  |
| `crude_recurrence_pct` | numeric |  |
| `median_months_to_recurrence` | numeric |  |
| `median_follow_up_months` | numeric |  |

### `marts.mart_survival`

Approx. rows: 1,098

| Column | Type | Description |
|---|---|---|
| `patient_id` | text |  |
| `patient_barcode` | text |  |
| `os_months` | numeric |  |
| `os_event` | integer |  |
| `dss_months` | numeric |  |
| `dss_event` | integer |  |
| `pfs_months` | numeric |  |
| `pfs_event` | integer |  |
| `dfs_months` | numeric |  |
| `dfs_event` | integer |  |
| `age_at_diagnosis` | bigint |  |
| `age_group` | text |  |
| `stage_major` | text |  |
| `stage_category` | text |  |
| `t_category` | text |  |
| `n_category` | text |  |
| `lymph_nodes_positive` | bigint |  |
| `histology_group` | text |  |
| `receptor_subtype` | text |  |
| `pam50_subtype` | text |  |
| `er_status` | text |  |
| `her2_status` | text |  |
| `race` | text |  |
| `race_ethnicity` | text |  |
| `site_type` | text |  |
| `volume_tier` | text |  |
| `hospital_name` | text |  |
| `is_benchmarkable` | boolean |  |
| `pathway_group` | text |  |
| `received_chemotherapy` | boolean |  |
| `received_radiation` | boolean |  |
| `received_endocrine` | boolean |  |
| `received_her2_targeted` | boolean |  |
| `days_to_chemotherapy` | bigint |  |
| `chemo_timing_group` | text |  |
| `chemo_delayed_over_90d` | boolean |  |
| `year_of_diagnosis` | bigint |  |

### `marts.mart_treatment_adherence`

Approx. rows: 3,028

| Column | Type | Description |
|---|---|---|
| `treatment_id` | text |  |
| `patient_id` | text |  |
| `pathway_modality` | text |  |
| `treatment_name` | text |  |
| `drug_class` | text |  |
| `number_of_cycles` | bigint |  |
| `standard_cycles` | numeric |  |
| `completed_standard_cycles` | boolean |  |
| `duration_days` | bigint |  |
| `endocrine_4_5y_or_more` | boolean |  |
| `number_of_fractions` | bigint |  |
| `treatment_outcome` | text |  |
| `progressed_on_treatment` | boolean |  |
| `hospital_name` | text |  |
| `stage_major` | text |  |
| `receptor_subtype` | text |  |
| `age_group` | text |  |
| `race_ethnicity` | text |  |
| `os_event` | integer |  |
| `any_progression_or_recurrence` | boolean |  |

### `marts.mart_treatment_delay`

Approx. rows: 2,641

| Column | Type | Description |
|---|---|---|
| `patient_id` | text |  |
| `interval_name` | text |  |
| `interval_days` | bigint |  |
| `exceeds_threshold` | boolean |  |
| `hospital_id` | text |  |
| `hospital_name` | text |  |
| `site_type` | text |  |
| `is_benchmarkable` | boolean |  |
| `year_of_diagnosis` | bigint |  |
| `stage_major` | text |  |
| `stage_category` | text |  |
| `receptor_subtype` | text |  |
| `age_group` | text |  |
| `race` | text |  |
| `ethnicity` | text |  |
| `race_ethnicity` | text |  |
| `country_of_residence` | text |  |
| `os_months` | numeric |  |
| `os_event` | integer |  |

### `marts.mart_treatment_pathways`

Approx. rows: 16

| Column | Type | Description |
|---|---|---|
| `pathway` | text |  |
| `n_patients` | bigint |  |
| `pct_of_patients` | numeric |  |
| `n_steps` | bigint |  |
| `mean_age` | numeric |  |
| `pct_stage_iii_iv` | numeric |  |
| `pct_triple_negative` | numeric |  |
| `median_treatment_span_days` | numeric |  |
| `median_days_to_first_adjuvant` | numeric |  |
| `mean_estimated_cost_usd` | numeric |  |
| `median_estimated_cost_usd` | numeric |  |
| `crude_mortality_pct` | numeric |  |
| `crude_recurrence_pct` | numeric |  |
| `median_follow_up_months` | numeric |  |
| `pct_fully_dated` | numeric |  |

## `analytics`

### `analytics.cox_coefficients`

Approx. rows: 62

| Column | Type | Description |
|---|---|---|
| `model` | text |  |
| `covariate` | text |  |
| `hazard_ratio` | double precision |  |
| `ci_lower` | double precision |  |
| `ci_upper` | double precision |  |
| `p_value` | double precision |  |
| `coef` | double precision |  |
| `se` | double precision |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.cox_model_fit`

Approx. rows: 6

| Column | Type | Description |
|---|---|---|
| `model` | text |  |
| `n` | bigint |  |
| `events` | bigint |  |
| `n_covariates` | bigint |  |
| `events_per_variable` | double precision |  |
| `penalizer` | double precision |  |
| `concordance` | double precision |  |
| `log_likelihood_ratio_p` | double precision |  |
| `aic_partial` | double precision |  |
| `status` | text |  |
| `caution` | text |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.cox_ph_tests`

Approx. rows: 62

| Column | Type | Description |
|---|---|---|
| `model` | text |  |
| `covariate` | text |  |
| `test_statistic` | double precision |  |
| `p_value` | double precision |  |
| `ph_assumption_ok` | boolean |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.delay_drivers`

Approx. rows: 27

| Column | Type | Description |
|---|---|---|
| `model` | text |  |
| `term` | text |  |
| `estimate` | double precision |  |
| `ci_lower` | double precision |  |
| `ci_upper` | double precision |  |
| `p_value` | double precision |  |
| `n` | bigint |  |
| `estimate_type` | text |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.disparity_rates`

Approx. rows: 35

| Column | Type | Description |
|---|---|---|
| `test_family` | text |  |
| `population` | text |  |
| `group_type` | text |  |
| `group_value` | text |  |
| `n` | bigint |  |
| `events` | bigint |  |
| `rate` | double precision |  |
| `ci_lower` | double precision |  |
| `ci_upper` | double precision |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.disparity_tests`

Approx. rows: 15

| Column | Type | Description |
|---|---|---|
| `test_family` | text |  |
| `population` | text |  |
| `group_type` | text |  |
| `method` | text |  |
| `statistic` | double precision |  |
| `dof` | double precision |  |
| `p_value` | double precision |  |
| `n` | bigint |  |
| `n_groups` | bigint |  |
| `effect_median_diff_days` | double precision |  |
| `p_value_fdr` | double precision |  |
| `significant_fdr_05` | boolean |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.hospital_risk_adjusted_delay`

Approx. rows: 8

| Column | Type | Description |
|---|---|---|
| `hospital_name` | text |  |
| `n` | bigint |  |
| `observed` | bigint |  |
| `expected` | double precision |  |
| `site_type` | text |  |
| `oe_ratio` | double precision |  |
| `oe_ci_lower` | double precision |  |
| `oe_ci_upper` | double precision |  |
| `observed_rate` | double precision |  |
| `expected_rate` | double precision |  |
| `network_rate` | double precision |  |
| `flag` | text |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.km_curves`

Approx. rows: 15,561

| Column | Type | Description |
|---|---|---|
| `cohort` | text |  |
| `endpoint` | text |  |
| `stratifier` | text |  |
| `group_value` | text |  |
| `time_months` | bigint |  |
| `survival` | double precision |  |
| `ci_lower` | double precision |  |
| `ci_upper` | double precision |  |
| `at_risk` | bigint |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.km_summary`

Approx. rows: 232

| Column | Type | Description |
|---|---|---|
| `cohort` | text |  |
| `endpoint` | text |  |
| `stratifier` | text |  |
| `group_value` | text |  |
| `n` | bigint |  |
| `events` | bigint |  |
| `median_survival_months` | double precision |  |
| `survival_5y` | double precision |  |
| `survival_5y_ci_lower` | double precision |  |
| `survival_5y_ci_upper` | double precision |  |
| `survival_10y` | double precision |  |
| `survival_10y_ci_lower` | double precision |  |
| `survival_10y_ci_upper` | double precision |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.kpi_alerts_detail`

Approx. rows: 51

| Column | Type | Description |
|---|---|---|
| `alert_id` | text |  |
| `kpi` | text |  |
| `kpi_label` | text |  |
| `entity_type` | text |  |
| `entity` | text |  |
| `period` | text |  |
| `current_value` | double precision |  |
| `baseline_value` | double precision |  |
| `pct_change` | double precision |  |
| `robust_z` | double precision |  |
| `n_current` | bigint |  |
| `severity` | text |  |
| `direction` | text |  |
| `message` | text |  |

### `analytics.logrank_tests`

Approx. rows: 42

| Column | Type | Description |
|---|---|---|
| `cohort` | text |  |
| `endpoint` | text |  |
| `stratifier` | text |  |
| `n_groups` | bigint |  |
| `n` | bigint |  |
| `test_statistic` | double precision |  |
| `degrees_of_freedom` | bigint |  |
| `p_value` | double precision |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.recurrence_feature_importance`

Approx. rows: 33

| Column | Type | Description |
|---|---|---|
| `model` | text |  |
| `feature` | text |  |
| `importance_mean` | double precision |  |
| `importance_sd` | double precision |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.recurrence_model_calibration`

Approx. rows: 24

| Column | Type | Description |
|---|---|---|
| `model` | text |  |
| `bin` | bigint |  |
| `mean_predicted` | double precision |  |
| `observed_rate` | double precision |  |
| `computed_at` | timestamp with time zone |  |

### `analytics.recurrence_model_metrics`

Approx. rows: 3

| Column | Type | Description |
|---|---|---|
| `model` | text |  |
| `n_total` | bigint |  |
| `n_events` | bigint |  |
| `event_rate` | double precision |  |
| `cv_roc_auc_mean` | double precision |  |
| `cv_roc_auc_sd` | double precision |  |
| `cv_pr_auc_mean` | double precision |  |
| `cv_brier_mean` | double precision |  |
| `holdout_roc_auc` | double precision |  |
| `holdout_pr_auc` | double precision |  |
| `holdout_brier` | double precision |  |
| `computed_at` | timestamp with time zone |  |

## `ops`

### `ops.dq_results`

Approx. rows: 216

| Column | Type | Description |
|---|---|---|
| `run_id` | text |  |
| `checked_at` | timestamp with time zone |  |
| `dataset` | text |  |
| `expectation` | text |  |
| `column_name` | text |  |
| `severity` | text |  |
| `success` | boolean |  |
| `observed` | jsonb |  |

### `ops.ingestion_watermarks`

Approx. rows: 1

| Column | Type | Description |
|---|---|---|
| `source` | text |  |
| `watermark` | text |  |
| `updated_at` | timestamp with time zone |  |

### `ops.kpi_alerts`

Approx. rows: 51

| Column | Type | Description |
|---|---|---|
| `alert_id` | text |  |
| `detected_at` | timestamp with time zone |  |
| `kpi` | text |  |
| `entity_type` | text |  |
| `entity` | text |  |
| `period` | text |  |
| `current_value` | double precision |  |
| `baseline_value` | double precision |  |
| `pct_change` | double precision |  |
| `robust_z` | double precision |  |
| `n_current` | integer |  |
| `severity` | text |  |
| `message` | text |  |

### `ops.pipeline_runs`

Approx. rows: 15

| Column | Type | Description |
|---|---|---|
| `run_id` | text |  |
| `pipeline` | text |  |
| `status` | text |  |
| `started_at` | timestamp with time zone |  |
| `finished_at` | timestamp with time zone |  |
| `rows_in` | integer |  |
| `rows_changed` | integer |  |
| `details` | jsonb |  |

## `ref`

### `ref.ref_agent_catalog`

Approx. rows: 65

| Column | Type | Description |
|---|---|---|
| `agent_key` | text |  |
| `canonical_agent` | text |  |
| `drug_class` | text |  |
| `pathway_modality` | text |  |
| `route` | text |  |
| `price_id` | text |  |
| `dosing_basis` | text |  |
| `units_per_administration` | numeric |  |
| `administrations_per_cycle` | numeric |  |
| `default_administrations` | numeric |  |
| `iv_infusion` | boolean |  |
| `dosing_assumption` | text |  |

### `ref.ref_ajcc_stage`

Approx. rows: 14

| Column | Type | Description |
|---|---|---|
| `stage_group` | text |  |
| `stage_major` | text |  |
| `stage_order` | integer |  |

### `ref.ref_cms_reference_prices`

Approx. rows: 35

| Column | Type | Description |
|---|---|---|
| `price_id` | text |  |
| `category` | text |  |
| `hcpcs_code` | text |  |
| `description` | text |  |
| `billing_unit` | text |  |
| `unit_price_usd` | numeric |  |
| `setting` | text |  |
| `price_basis` | text |  |
| `source_file` | text |  |
| `source_url` | text |  |
| `effective_period` | text |  |

### `ref.ref_procedure_cost_rules`

Approx. rows: 8

| Column | Type | Description |
|---|---|---|
| `rule_id` | text |  |
| `modality` | text |  |
| `price_id` | text |  |
| `quantity_basis` | text |  |
| `quantity_multiplier` | double precision |  |
| `assumption` | text |  |

### `ref.ref_site_classification`

Approx. rows: 40

| Column | Type | Description |
|---|---|---|
| `tss_code` | text |  |
| `site_type` | text |  |
| `is_treating_facility` | boolean |  |
