-- Descriptive equity metrics by patient group. Guideline-concordance proxies:
--  * chemo_indicated: triple-negative or HER2+ disease, stage II-III (systemic therapy strongly indicated)
--  * her2_targeted among HER2+ ; endocrine therapy among HR+
with p as (select * from {{ ref('mart_patient_360') }}),
g as (
    select 'Race' as group_type, race as group_value, p.* from p
    union all select 'Ethnicity', ethnicity, p.* from p
    union all select 'Race/ethnicity', race_ethnicity, p.* from p
    union all select 'Age group', age_group, p.* from p
    union all select 'Site type', site_type, p.* from p
    union all select 'Country of residence', country_of_residence, p.* from p
)
select
    group_type, group_value,
    count(*)                                                                                          as n_patients,
    round(avg(age_at_diagnosis), 1)                                                                   as mean_age,
    round(100.0 * avg((stage_major in ('III', 'IV'))::int), 1)                                        as pct_stage_iii_iv,
    round(100.0 * avg((receptor_subtype = 'Triple negative')::int), 1)                                as pct_triple_negative,
    round((percentile_cont(0.5) within group (order by days_to_chemotherapy) filter (where days_to_chemotherapy between 0 and 730))::numeric, 1) as median_days_to_chemotherapy,
    round(100.0 * avg(chemo_delayed_over_90d::int) filter (where days_to_chemotherapy between 0 and 730), 1) as pct_chemo_over_90d,
    count(*) filter (where receptor_subtype in ('Triple negative', 'HR-/HER2+', 'HR+/HER2+') and stage_major in ('II', 'III')) as n_chemo_indicated,
    round(100.0 * avg(received_chemotherapy::int) filter (where receptor_subtype in ('Triple negative', 'HR-/HER2+', 'HR+/HER2+') and stage_major in ('II', 'III')), 1) as pct_chemo_when_indicated,
    round(100.0 * avg(received_her2_targeted::int) filter (where her2_status = 'Positive'), 1)        as pct_her2_targeted_among_her2_pos,
    round(100.0 * avg(received_endocrine::int) filter (where hr_status = 'Positive'), 1)              as pct_endocrine_among_hr_pos,
    round(100.0 * avg(received_radiation::int), 1)                                                    as pct_radiation,
    round(100.0 * avg(os_event), 1)                                                                   as crude_mortality_pct,
    round(100.0 * avg(any_progression_or_recurrence::int), 1)                                         as crude_recurrence_pct
from g
group by group_type, group_value
