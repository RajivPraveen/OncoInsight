{{ config(materialized='incremental', unique_key='treatment_id', incremental_strategy='delete+insert',
          on_schema_change='sync_all_columns') }}
-- Systemic therapy administrations/statements (subset of fact_treatment with drug detail).
select
    m.treatment_id,
    m.patient_id,
    m.fhir_resource_type,
    m.status,
    m.agent_raw,
    coalesce(cat.canonical_agent, m.agent_raw)  as canonical_agent,
    cat.drug_class,
    m.days_to_treatment_start                   as start_day,
    m.days_to_treatment_end                     as end_day,
    m.number_of_cycles,
    m.delivered_dose,
    m.delivered_dose_unit,
    m.route,
    m.treatment_intent,
    m.treatment_outcome,
    m.clinical_trial,
    m._loaded_at
from {{ ref('stg_fhir__medications') }} m
left join {{ ref('ref_agent_catalog') }} cat on cat.agent_key = m.agent_key
{{ incremental_loaded_at('m._loaded_at') }}
