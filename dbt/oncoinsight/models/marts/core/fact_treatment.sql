{{ config(
    materialized='incremental',
    unique_key='treatment_id',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    post_hook=["delete from {{ this }} t where not exists (select 1 from {{ ref('int_treatment_events') }} e where e.treatment_id = t.treatment_id)"]
) }}
-- Grain: one delivered-or-documented treatment record (surgery, radiation course, systemic agent).
with costs as (
    select treatment_id, sum(estimated_amount_usd) as estimated_cost_usd
    from {{ ref('int_estimated_cost_lines') }}
    group by treatment_id
)
select
    e.treatment_id,
    e.patient_id,
    e.condition_id                                            as diagnosis_id,
    e.hospital_id,
    e.fhir_resource_type,
    e.status,
    e.is_delivered,
    e.pathway_modality,
    e.pathway_group,
    case when e.canonical_agent is not null then md5('agent|' || e.canonical_agent)
         else md5('proc|' || e.pathway_modality) end          as treatment_key,
    coalesce(e.canonical_agent, e.treatment_name)             as treatment_name,
    e.drug_class,
    e.start_day,
    e.start_day_imputed,
    e.end_day,
    e.end_day - e.start_day                                   as duration_days,
    e.treatment_intent,
    e.treatment_outcome,
    e.number_of_cycles,
    e.number_of_fractions,
    e.delivered_dose_cgy,
    e.margin_status,
    coalesce(c.estimated_cost_usd, 0)                         as estimated_cost_usd,
    c.treatment_id is not null                                as is_priced,
    e._loaded_at
from {{ ref('int_treatment_events') }} e
left join costs c on c.treatment_id = e.treatment_id
{{ incremental_loaded_at('e._loaded_at') }}
