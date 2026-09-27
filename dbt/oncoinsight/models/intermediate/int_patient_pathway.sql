with steps as (select * from {{ ref('int_pathway_steps') }}),
agg as (
    select
        patient_id,
        string_agg(pathway_group, ' → ' order by step_number)      as pathway,
        count(*)                                                   as n_pathway_steps,
        min(first_start_day)                                       as first_treatment_day,
        max(last_end_day)                                          as last_treatment_day,
        min(first_start_day) filter (where pathway_group = 'Surgery')       as surgery_day,
        min(first_start_day) filter (where pathway_group = 'Chemotherapy')  as chemo_start_day,
        max(last_end_day)    filter (where pathway_group = 'Chemotherapy')  as chemo_end_day,
        min(first_start_day) filter (where pathway_group = 'Radiation')     as radiation_start_day,
        min(first_start_day) filter (where pathway_group = 'Endocrine')     as endocrine_start_day,
        min(first_start_day) filter (where pathway_group = 'HER2-targeted') as her2_start_day,
        min(first_start_day) filter (where pathway_group <> 'Surgery' and first_start_day >= 0) as first_adjuvant_day
    from steps
    group by patient_id
),
delivered as (
    select
        patient_id,
        bool_or(pathway_modality = 'Surgery')        as received_surgery,
        bool_or(pathway_modality = 'Chemotherapy')   as received_chemotherapy,
        bool_or(pathway_modality = 'Radiation')      as received_radiation,
        bool_or(pathway_modality = 'Endocrine')      as received_endocrine,
        bool_or(pathway_modality = 'HER2-targeted')  as received_her2_targeted,
        bool_or(pathway_group = 'Other systemic')    as received_other_systemic,
        count(*)                                     as n_treatment_records,
        count(distinct canonical_agent)              as n_distinct_agents,
        count(*) filter (where start_day is null and pathway_group is not null) as n_undated_delivered
    from {{ ref('int_treatment_events') }}
    where is_delivered
    group by patient_id
)
select
    p.patient_id,
    coalesce(a.pathway, 'No dated treatment recorded')        as pathway,
    coalesce(a.n_pathway_steps, 0)                            as n_pathway_steps,
    a.first_treatment_day, a.last_treatment_day, a.surgery_day, a.chemo_start_day, a.chemo_end_day,
    a.radiation_start_day, a.endocrine_start_day, a.her2_start_day, a.first_adjuvant_day,
    (a.chemo_start_day < coalesce(a.surgery_day, 0))          as neoadjuvant_chemotherapy,
    coalesce(d.received_surgery, false)        as received_surgery,
    coalesce(d.received_chemotherapy, false)   as received_chemotherapy,
    coalesce(d.received_radiation, false)      as received_radiation,
    coalesce(d.received_endocrine, false)      as received_endocrine,
    coalesce(d.received_her2_targeted, false)  as received_her2_targeted,
    coalesce(d.received_other_systemic, false) as received_other_systemic,
    coalesce(d.n_treatment_records, 0)         as n_treatment_records,
    coalesce(d.n_distinct_agents, 0)           as n_distinct_agents,
    coalesce(d.n_undated_delivered, 0)         as n_undated_delivered,
    coalesce(d.n_undated_delivered, 0) = 0     as pathway_is_complete,
    a.last_treatment_day - a.first_treatment_day as treatment_span_days
from {{ ref('stg_fhir__patients') }} p
left join agg a on a.patient_id = p.patient_id
left join delivered d on d.patient_id = p.patient_id
