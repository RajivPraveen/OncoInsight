{{ config(materialized='incremental', unique_key='observation_id', incremental_strategy='delete+insert',
          on_schema_change='sync_all_columns') }}
-- Clinical observations: staging, pathology counts, biomarkers ("lab results"), disease status, recurrence.
select
    observation_id, patient_id, condition_id as diagnosis_id, encounter_id, category,
    observation_code, observation_name, value_text, value_integer, method, biomarker,
    days_from_diagnosis, anchored_effective_date, _loaded_at
from {{ ref('stg_fhir__observations') }}
{{ incremental_loaded_at() }}
