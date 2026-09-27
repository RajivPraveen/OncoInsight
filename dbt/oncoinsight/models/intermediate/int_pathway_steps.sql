-- Ordered treatment pathway steps per patient: the first start of each modality group.
with firsts as (
    select
        patient_id,
        pathway_group,
        min(start_day)                           as first_start_day,
        max(coalesce(end_day, start_day))        as last_end_day,
        count(*)                                 as n_records
    from {{ ref('int_treatment_events') }}
    where is_delivered and pathway_group is not null and start_day is not null
    group by patient_id, pathway_group
),
ordered as (
    select
        f.*,
        row_number() over (
            partition by patient_id
            order by first_start_day,
                     case pathway_group when 'Surgery' then 1 when 'Chemotherapy' then 2 when 'HER2-targeted' then 3
                                        when 'Radiation' then 4 when 'Endocrine' then 5 else 6 end
        ) as step_number
    from firsts f
)
select
    o.*,
    lag(pathway_group)   over (partition by patient_id order by step_number) as previous_group,
    first_start_day - lag(first_start_day) over (partition by patient_id order by step_number) as days_since_previous_step,
    first_start_day - lag(last_end_day)    over (partition by patient_id order by step_number) as days_since_previous_end
from ordered o
