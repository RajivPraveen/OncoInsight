-- Operational KPIs by diagnosis year, for the network and each benchmarkable site. Feeds the operations
-- dashboard and the automated KPI monitor. (TCGA provides diagnosis year, not month.)
with p as (select * from {{ ref('mart_patient_360') }} where year_of_diagnosis is not null),
scoped as (
    select 'Network' as entity_type, 'All sites' as entity, p.* from p
    union all
    select 'Hospital', hospital_name, p.* from p where is_benchmarkable
)
select
    entity_type, entity, year_of_diagnosis,
    count(*)                                                                         as new_diagnoses,
    count(*) filter (where stage_major in ('III', 'IV'))                             as advanced_stage_diagnoses,
    count(*) filter (where received_chemotherapy)                                     as chemotherapy_patients,
    count(*) filter (where received_radiation)                                        as radiation_patients,
    count(*) filter (where received_endocrine)                                        as endocrine_patients,
    count(*) filter (where received_surgery)                                          as surgery_patients,
    round((percentile_cont(0.5) within group (order by days_to_chemotherapy) filter (where days_to_chemotherapy between 0 and 730))::numeric, 1) as median_days_to_chemotherapy,
    count(*) filter (where days_to_chemotherapy between 0 and 730)                    as n_timed_chemotherapy,
    round(100.0 * avg(chemo_delayed_over_90d::int) filter (where days_to_chemotherapy between 0 and 730), 1) as pct_chemo_over_90d,
    round((percentile_cont(0.5) within group (order by days_to_radiation) filter (where days_to_radiation between 0 and 730))::numeric, 1) as median_days_to_radiation,
    round(100.0 * avg(any_progression_or_recurrence::int), 1)                         as recurrence_rate_pct,
    round(100.0 * avg(os_event), 1)                                                   as mortality_rate_pct,
    round(avg(total_estimated_cost_usd), 0)                                           as mean_estimated_cost_usd
from scoped
group by entity_type, entity, year_of_diagnosis
