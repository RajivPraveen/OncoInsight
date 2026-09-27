{{ config(materialized='incremental', unique_key='encounter_id', incremental_strategy='delete+insert',
          on_schema_change='sync_all_columns') }}
select encounter_id, patient_id, condition_id as diagnosis_id, hospital_id, status, encounter_class,
       timepoint, days_from_diagnosis, anchored_encounter_date, _loaded_at
from {{ ref('stg_fhir__encounters') }}
{{ incremental_loaded_at() }}
