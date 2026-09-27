select
    id                                          as observation_id,
    patient_id,
    condition_id,
    encounter_id,
    category,
    code                                        as observation_code,
    coalesce(code_display, code_text)           as observation_name,
    value_text,
    value_integer,
    method,
    biomarker,
    days_from_diagnosis,
    effective_date::date                        as anchored_effective_date,
    recurrence_site,
    days_to_recurrence,
    days_to_progression,
    _loaded_at
from {{ source('fhir', 'fhir_observation') }}
where not _is_deleted
