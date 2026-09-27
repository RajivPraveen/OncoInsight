select
    c.id                                        as condition_id,
    c.patient_id,
    c.icd10_code,
    c.diagnosis_text,
    coalesce(c.is_primary, true)                as is_primary,
    c.days_from_index_diagnosis,
    c.year_of_diagnosis,
    c.morphology_code,
    case
        when c.morphology_code = '8500/3' then 'Invasive ductal carcinoma'
        when c.morphology_code = '8520/3' then 'Invasive lobular carcinoma'
        when c.morphology_code = '8522/3' then 'Mixed ductal and lobular'
        when c.morphology_code in ('8480/3', '8481/3') then 'Mucinous carcinoma'
        when c.morphology_code = '8510/3' then 'Medullary carcinoma'
        when c.morphology_code is null then 'Unknown'
        else 'Other histology'
    end                                         as histology_group,
    c.classification_of_tumor,
    c.ajcc_staging_edition,
    c.method_of_diagnosis,
    c.prior_treatment,
    c.prior_malignancy,
    c.laterality,
    c.onset_date::date                          as anchored_diagnosis_date,
    coalesce(c.stage_group, 'Unknown')          as stage_group,
    {{ stage_major('c.stage_group') }}          as stage_major,
    c._loaded_at
from {{ source('fhir', 'fhir_condition') }} c
where not c._is_deleted
