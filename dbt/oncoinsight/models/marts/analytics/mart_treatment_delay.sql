-- Long-format time-to-treatment intervals (days) with stratifiers for delay benchmarking.
with p as (select * from {{ ref('mart_patient_360') }}),
intervals as (
    select patient_id, 'Diagnosis → Chemotherapy' as interval_name, days_to_chemotherapy as interval_days from p
    union all select patient_id, 'Diagnosis → Radiation', days_to_radiation from p
    union all select patient_id, 'Diagnosis → Endocrine therapy', days_to_endocrine from p
    union all select patient_id, 'Diagnosis → First adjuvant treatment', days_to_first_adjuvant_treatment from p
    union all
    select pw.patient_id, 'Chemotherapy end → Radiation', pw.radiation_start_day - pw.chemo_end_day
    from {{ ref('int_patient_pathway') }} pw
    where pw.radiation_start_day > pw.chemo_start_day
)
select
    i.patient_id, i.interval_name, i.interval_days,
    case when i.interval_name = 'Diagnosis → Chemotherapy' then i.interval_days > {{ var('chemo_delay_threshold_days') }} end as exceeds_threshold,
    p.hospital_id, p.hospital_name, p.site_type, p.is_benchmarkable, p.year_of_diagnosis,
    p.stage_major, p.stage_category, p.receptor_subtype, p.age_group, p.race, p.ethnicity, p.race_ethnicity,
    p.country_of_residence, p.os_months, p.os_event
from intervals i
join p on p.patient_id = i.patient_id
-- adjuvant intervals only (neoadjuvant starts are negative); drop implausible >2y gaps as data errors
where i.interval_days is not null and i.interval_days between 0 and 730
