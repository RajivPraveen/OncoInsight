-- Crude recurrence rates by clinical factor (grouping sets -> long format for BI).
with r as (select * from {{ ref('mart_recurrence') }})
select
    case when grouping(stage_major) = 0 then 'Stage'
         when grouping(receptor_subtype) = 0 then 'Receptor subtype'
         when grouping(pathway_group) = 0 then 'Treatment pathway'
         when grouping(age_group) = 0 then 'Age group'
         when grouping(t_category) = 0 then 'Tumour (T) category'
         when grouping(n_category) = 0 then 'Nodal (N) category'
         else 'All patients' end                                             as factor,
    coalesce(stage_major, receptor_subtype, pathway_group, age_group, t_category, n_category, 'All') as factor_value,
    count(*)                                                                 as n_patients,
    sum(recurrence_event)                                                    as n_recurrences,
    round(100.0 * avg(recurrence_event), 1)                                  as crude_recurrence_pct,
    round((percentile_cont(0.5) within group (order by time_to_event_months) filter (where recurrence_event = 1))::numeric, 1) as median_months_to_recurrence,
    round((percentile_cont(0.5) within group (order by time_to_event_months))::numeric, 1)       as median_follow_up_months
from r
group by grouping sets ((stage_major), (receptor_subtype), (pathway_group), (age_group), (t_category), (n_category), ())
