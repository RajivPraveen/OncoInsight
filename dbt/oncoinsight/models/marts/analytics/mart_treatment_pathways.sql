-- Pathway-level utilisation, timing, outcome and cost summary. Pathways with fewer than 10 patients are
-- grouped to protect small cells and keep comparisons stable.
with p as (select * from {{ ref('mart_patient_360') }}),
counts as (select pathway, count(*) as n from p group by pathway),
labelled as (
    select p.*, case when c.n >= 10 then p.pathway else 'Other pathways (n<10 each)' end as pathway_label
    from p join counts c using (pathway)
)
select
    pathway_label                                                        as pathway,
    count(*)                                                             as n_patients,
    round(100.0 * count(*) / sum(count(*)) over (), 1)                   as pct_of_patients,
    max(n_pathway_steps)                                                 as n_steps,
    round(avg(age_at_diagnosis), 1)                                      as mean_age,
    round(100.0 * avg((stage_major in ('III', 'IV'))::int), 1)           as pct_stage_iii_iv,
    round(100.0 * avg((receptor_subtype = 'Triple negative')::int), 1)   as pct_triple_negative,
    round((percentile_cont(0.5) within group (order by treatment_span_days))::numeric, 1)     as median_treatment_span_days,
    round((percentile_cont(0.5) within group (order by days_to_first_adjuvant_treatment))::numeric, 1) as median_days_to_first_adjuvant,
    round(avg(total_estimated_cost_usd), 0)                              as mean_estimated_cost_usd,
    round((percentile_cont(0.5) within group (order by total_estimated_cost_usd))::numeric, 1) as median_estimated_cost_usd,
    round(100.0 * avg(os_event), 1)                                      as crude_mortality_pct,
    round(100.0 * avg(any_progression_or_recurrence::int), 1)            as crude_recurrence_pct,
    round((percentile_cont(0.5) within group (order by os_months))::numeric, 1)               as median_follow_up_months,
    round(100.0 * avg(pathway_is_complete::int), 1)                      as pct_fully_dated
from labelled
group by pathway_label
