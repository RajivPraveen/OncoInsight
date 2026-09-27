-- Source -> target transitions for the treatment-journey Sankey: Diagnosis -> ordered modality steps -> outcome.
with steps as (
    select patient_id, step_number, pathway_group from {{ ref('int_pathway_steps') }} where step_number <= 5
),
outcome as (
    select patient_id,
           case when os_event = 1 then 'Deceased'
                when any_progression_or_recurrence then 'Recurrence / progression'
                else 'Alive, no recurrence recorded' end as outcome_label
    from {{ ref('mart_patient_360') }}
),
nodes as (
    select patient_id, 0 as step_number, 'Diagnosis' as label from outcome
    union all
    select patient_id, step_number, step_number || '. ' || pathway_group from steps
),
edges as (
    select n.patient_id, n.label as source,
           coalesce(lead(n.label) over (partition by n.patient_id order by n.step_number), 'Outcome: ' || o.outcome_label) as target,
           n.step_number
    from nodes n join outcome o on o.patient_id = n.patient_id
)
select source, target, min(step_number) as source_step, count(*) as n_patients
from edges
group by source, target
