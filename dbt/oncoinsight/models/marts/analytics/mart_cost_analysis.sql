-- Estimated treatment cost (CMS 2026 reference prices) by pathway, stage, subtype and site type.
with p as (select * from {{ ref('mart_patient_360') }} where n_treatment_records > 0),
lab as (
    select p.*, case when count(*) over (partition by pathway) >= 10 then pathway else 'Other pathways (n<10 each)' end as pathway_label
    from p
)
select
    case when grouping(pathway_label) = 0 then 'Treatment pathway'
         when grouping(stage_major) = 0 then 'Stage'
         when grouping(receptor_subtype) = 0 then 'Receptor subtype'
         when grouping(site_type) = 0 then 'Site type'
         else 'All patients' end                                               as dimension,
    coalesce(pathway_label, stage_major, receptor_subtype, site_type, 'All')     as dimension_value,
    count(*)                                                                   as n_patients,
    round(avg(total_estimated_cost_usd), 0)                                    as mean_cost_usd,
    round((percentile_cont(0.5) within group (order by total_estimated_cost_usd))::numeric, 1)     as median_cost_usd,
    round((percentile_cont(0.25) within group (order by total_estimated_cost_usd))::numeric, 1)     as p25_cost_usd,
    round((percentile_cont(0.75) within group (order by total_estimated_cost_usd))::numeric, 1)     as p75_cost_usd,
    round(100.0 * sum(drug_cost_usd) / nullif(sum(total_estimated_cost_usd), 0), 1)           as pct_drug,
    round(100.0 * sum(administration_cost_usd) / nullif(sum(total_estimated_cost_usd), 0), 1) as pct_administration,
    round(100.0 * sum(radiation_cost_usd) / nullif(sum(total_estimated_cost_usd), 0), 1)      as pct_radiation,
    round(100.0 * sum(surgery_cost_usd) / nullif(sum(total_estimated_cost_usd), 0), 1)        as pct_surgery,
    round(100.0 * avg(os_event), 1)                                            as crude_mortality_pct,
    round(100.0 * avg(any_progression_or_recurrence::int), 1)                  as crude_recurrence_pct,
    round(100.0 * avg(has_unpriced_treatment::int), 1)                         as pct_with_unpriced_treatment
from lab
group by grouping sets ((pathway_label), (stage_major), (receptor_subtype), (site_type), ())
