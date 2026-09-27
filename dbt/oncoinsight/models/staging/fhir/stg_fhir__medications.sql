select
    id                                          as treatment_id,
    fhir_resource_type,
    patient_id,
    condition_id,
    status,
    status in ('completed', 'in-progress', 'active') as is_delivered,
    modality                                    as source_modality,
    agent                                       as agent_raw,
    lower(trim(agent))                          as agent_key,
    days_to_treatment_start,
    days_to_treatment_end,
    treatment_intent,
    treatment_outcome,
    number_of_cycles,
    delivered_dose,
    delivered_dose_unit,
    route,
    clinical_trial,
    organization_id                             as hospital_id,
    _loaded_at
from {{ source('fhir', 'fhir_medication') }}
where not _is_deleted
