select
    id                                          as encounter_id,
    patient_id,
    condition_id,
    status,
    encounter_class,
    timepoint,
    days_from_diagnosis,
    period_start::date                          as anchored_encounter_date,
    organization_id                             as hospital_id,
    _loaded_at
from {{ source('fhir', 'fhir_encounter') }}
where not _is_deleted
