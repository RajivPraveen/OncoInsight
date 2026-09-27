-- Patient-level ordered pathway steps with cohort attributes, so journey visuals (Sankey, step timing)
-- can be re-aggregated for any filtered cohort in the dashboard/API.
select
    s.patient_id,
    s.step_number,
    s.pathway_group,
    s.first_start_day,
    s.last_end_day,
    s.previous_group,
    s.days_since_previous_step,
    s.days_since_previous_end,
    p.year_of_diagnosis, p.stage_major, p.receptor_subtype, p.age_group, p.site_type, p.hospital_name,
    p.race_ethnicity, p.os_event, p.any_progression_or_recurrence
from {{ ref('int_pathway_steps') }} s
join {{ ref('mart_patient_360') }} p on p.patient_id = s.patient_id
