-- One index primary breast cancer diagnosis per patient, enriched with pathologic TNM and lymph node counts.
with ranked as (
    select
        c.*,
        row_number() over (
            partition by c.patient_id
            order by (c.days_from_index_diagnosis = 0) desc nulls last,
                     abs(coalesce(c.days_from_index_diagnosis, 0)), c.condition_id
        ) as rn
    from {{ ref('stg_fhir__conditions') }} c
    where c.is_primary
),
tnm as (
    select
        condition_id,
        max(value_text)    filter (where observation_code = '21899-0') as pathologic_t,
        max(value_text)    filter (where observation_code = '21900-6') as pathologic_n,
        max(value_text)    filter (where observation_code = '21901-4') as pathologic_m,
        max(value_integer) filter (where observation_code = '21893-3') as lymph_nodes_positive,
        max(value_integer) filter (where observation_code = '21894-1') as lymph_nodes_examined
    from {{ ref('stg_fhir__observations') }}
    where category in ('tnm-staging', 'pathology')
    group by condition_id
)
select
    r.condition_id,
    r.patient_id,
    r.icd10_code,
    r.diagnosis_text,
    r.morphology_code,
    r.histology_group,
    r.year_of_diagnosis,
    r.anchored_diagnosis_date,
    r.laterality,
    r.stage_group,
    r.stage_major,
    r.ajcc_staging_edition,
    r.method_of_diagnosis,
    r.prior_malignancy,
    t.pathologic_t,
    t.pathologic_n,
    t.pathologic_m,
    coalesce(substring(t.pathologic_t from '^(T[0-4X]|Tis)'), 'Unknown') as t_category,
    coalesce(substring(t.pathologic_n from '^(N[0-3X])'), 'Unknown')     as n_category,
    case when t.pathologic_m ~ 'M1' then 'M1'
         when t.pathologic_m ~ 'M0' then 'M0'
         when t.pathologic_m = 'MX' then 'MX' else 'Unknown' end        as m_category,
    t.lymph_nodes_positive,
    t.lymph_nodes_examined,
    r._loaded_at
from ranked r
left join tnm t on t.condition_id = r.condition_id
where r.rn = 1
