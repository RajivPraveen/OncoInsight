-- Patient 360: one row per TCGA-BRCA patient combining demographics, diagnosis, biomarkers, treatment
-- pathway and timing, follow-up, outcomes and estimated cost.
with cost as (
    select patient_id,
           sum(estimated_amount_usd)                                              as total_estimated_cost_usd,
           sum(estimated_amount_usd) filter (where cost_component = 'drug')         as drug_cost_usd,
           sum(estimated_amount_usd) filter (where cost_component = 'administration') as administration_cost_usd,
           sum(estimated_amount_usd) filter (where cost_component = 'radiation')    as radiation_cost_usd,
           sum(estimated_amount_usd) filter (where cost_component = 'surgery')      as surgery_cost_usd
    from {{ ref('fact_estimated_cost') }}
    group by patient_id
),
unpriced as (
    select patient_id, bool_or(is_delivered and not is_priced) as has_unpriced_treatment
    from {{ ref('fact_treatment') }}
    group by patient_id
)
select
    p.patient_id,
    p.patient_barcode,
    -- demographics
    p.gender, p.age_at_diagnosis, p.age_group, p.race, p.ethnicity, p.race_ethnicity, p.country_of_residence,
    -- site
    h.hospital_id, h.hospital_name, h.site_type, h.is_treating_facility, h.volume_tier, h.is_benchmarkable,
    -- diagnosis
    d.year_of_diagnosis, d.anchored_diagnosis_date, d.stage_group, d.stage_major, s.stage_category,
    d.t_category, d.n_category, d.m_category, d.lymph_nodes_positive, d.lymph_nodes_examined,
    d.histology_group, d.laterality,
    b.er_status, b.pr_status, b.her2_status, b.hr_status, b.receptor_subtype, fd.pam50_subtype,
    -- pathway & timing (days from index diagnosis)
    pw.pathway, pw.n_pathway_steps, pw.pathway_is_complete, pw.n_undated_delivered,
    pw.received_surgery, pw.received_chemotherapy, pw.received_radiation, pw.received_endocrine,
    pw.received_her2_targeted, pw.received_other_systemic, coalesce(pw.neoadjuvant_chemotherapy, false) as neoadjuvant_chemotherapy,
    pw.n_treatment_records, pw.n_distinct_agents,
    pw.chemo_start_day                         as days_to_chemotherapy,
    pw.radiation_start_day                     as days_to_radiation,
    pw.endocrine_start_day                     as days_to_endocrine,
    pw.her2_start_day                          as days_to_her2_targeted,
    pw.first_adjuvant_day                      as days_to_first_adjuvant_treatment,
    pw.chemo_end_day - pw.chemo_start_day      as chemotherapy_duration_days,
    pw.treatment_span_days,
    case when pw.chemo_start_day is null then null
         when pw.chemo_start_day < 0 then 'Neoadjuvant'
         when pw.chemo_start_day <= 30 then '0-30 days'
         when pw.chemo_start_day <= 60 then '31-60 days'
         when pw.chemo_start_day <= {{ var('chemo_delay_threshold_days') }} then '61-90 days'
         else '>90 days' end                   as chemo_timing_group,
    pw.chemo_start_day > {{ var('chemo_delay_threshold_days') }} as chemo_delayed_over_90d,
    -- follow-up & outcomes
    o.n_follow_up_visits,
    round(o.last_contact_day / 365.25, 2)      as follow_up_years,
    case when o.last_contact_day > 0 then round(o.n_follow_up_visits / (o.last_contact_day / 365.25), 2) end as follow_up_visits_per_year,
    o.last_disease_status,
    o.vital_status,
    o.os_months, o.os_event, o.dss_months, o.dss_event, o.pfs_months, o.pfs_event, o.dfs_months, o.dfs_event,
    o.any_progression_or_recurrence,
    o.first_recurrence_day                      as days_to_recurrence,
    o.recurrence_type,
    -- estimated cost (CMS 2026 reference prices)
    coalesce(c.total_estimated_cost_usd, 0)     as total_estimated_cost_usd,
    coalesce(c.drug_cost_usd, 0)                as drug_cost_usd,
    coalesce(c.administration_cost_usd, 0)      as administration_cost_usd,
    coalesce(c.radiation_cost_usd, 0)           as radiation_cost_usd,
    coalesce(c.surgery_cost_usd, 0)             as surgery_cost_usd,
    coalesce(u.has_unpriced_treatment, false)   as has_unpriced_treatment
from {{ ref('dim_patient') }} p
left join {{ ref('dim_hospital') }} h           on h.hospital_id = p.hospital_id
left join {{ ref('int_primary_diagnosis') }} d  on d.patient_id = p.patient_id
left join {{ ref('fact_diagnosis') }} fd        on fd.patient_id = p.patient_id
left join {{ ref('dim_stage') }} s              on s.stage_group = d.stage_group
left join {{ ref('int_biomarker_status') }} b   on b.patient_id = p.patient_id
left join {{ ref('int_patient_pathway') }} pw   on pw.patient_id = p.patient_id
left join {{ ref('fact_outcome') }} o           on o.patient_id = p.patient_id
left join cost c                                on c.patient_id = p.patient_id
left join unpriced u                            on u.patient_id = p.patient_id
