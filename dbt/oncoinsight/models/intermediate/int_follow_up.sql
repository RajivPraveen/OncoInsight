-- Follow-up intensity, last known disease status and first recurrence per patient (GDC follow-up forms).
with enc as (
    select patient_id,
           count(*) filter (where timepoint = 'Follow-up')  as n_follow_up_visits,
           max(days_from_diagnosis)                        as last_encounter_day
    from {{ ref('stg_fhir__encounters') }}
    group by patient_id
),
status as (
    select distinct on (patient_id)
           patient_id, value_text as last_disease_status, days_from_diagnosis as last_status_day
    from {{ ref('stg_fhir__observations') }}
    where category = 'disease-status'
    order by patient_id, days_from_diagnosis desc nulls last
),
recur as (
    select distinct on (patient_id)
           patient_id, days_from_diagnosis as first_recurrence_day, value_text as recurrence_type,
           recurrence_site
    from {{ ref('stg_fhir__observations') }}
    where category = 'recurrence'
    order by patient_id, days_from_diagnosis nulls last
)
select
    p.patient_id,
    coalesce(e.n_follow_up_visits, 0)                            as n_follow_up_visits,
    greatest(e.last_encounter_day, s.last_status_day, p.days_to_death) as last_contact_day,
    s.last_disease_status,
    r.patient_id is not null                                     as gdc_recurrence_recorded,
    r.first_recurrence_day,
    r.recurrence_type,
    r.recurrence_site
from {{ ref('stg_fhir__patients') }} p
left join enc e    on e.patient_id = p.patient_id
left join status s on s.patient_id = p.patient_id
left join recur r  on r.patient_id = p.patient_id
