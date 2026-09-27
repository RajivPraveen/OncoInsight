select
    id                                          as treatment_id,
    'Procedure'                                 as fhir_resource_type,
    patient_id,
    condition_id,
    status,
    status in ('completed', 'in-progress')      as is_delivered,
    modality                                    as source_modality,
    treatment_type,
    days_to_treatment_start,
    days_to_treatment_end,
    treatment_intent,
    treatment_outcome,
    number_of_cycles,
    number_of_fractions,
    delivered_dose                              as delivered_dose_cgy,
    margin_status,
    body_sites,
    organization_id                             as hospital_id,
    _loaded_at
from {{ source('fhir', 'fhir_procedure') }}
where not _is_deleted
