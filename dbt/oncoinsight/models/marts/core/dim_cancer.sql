select distinct
    md5(coalesce(morphology_code, 'NA') || '|' || coalesce(icd10_code, 'NA')) as cancer_key,
    morphology_code,
    histology_group,
    icd10_code,
    diagnosis_text
from {{ ref('int_primary_diagnosis') }}
