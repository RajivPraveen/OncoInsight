select
    id                                          as patient_id,
    gdc_barcode                                 as patient_barcode,
    gender,
    birth_year,
    coalesce(deceased, false)                   as is_deceased,
    deceased_date::date                         as anchored_death_date,
    coalesce(race, 'Not reported')              as race,
    coalesce(ethnicity, 'Not reported')         as ethnicity,
    age_at_diagnosis_years,
    coalesce(age_is_obfuscated, false)          as age_is_obfuscated,
    days_to_death,
    vital_status,
    country_of_residence,
    organization_id                             as hospital_id,
    _loaded_at
from {{ source('fhir', 'fhir_patient') }}
where not _is_deleted
