select
    p.patient_id,
    p.patient_barcode,
    p.gender,
    coalesce(p.age_at_diagnosis_years, r.age_at_diagnosis)     as age_at_diagnosis,
    {{ age_group('coalesce(p.age_at_diagnosis_years, r.age_at_diagnosis)') }} as age_group,
    p.age_is_obfuscated,
    p.birth_year,
    p.race,
    p.ethnicity,
    case when p.ethnicity = 'Hispanic or Latino' then 'Hispanic'
         when p.race = 'White' then 'Non-Hispanic White'
         when p.race = 'Black or African American' then 'Non-Hispanic Black'
         when p.race = 'Asian' then 'Non-Hispanic Asian'
         when p.race = 'Not reported' then 'Not reported'
         else 'Other' end                                       as race_ethnicity,
    coalesce(p.country_of_residence, 'Not reported')           as country_of_residence,
    p.vital_status,
    p.hospital_id,
    p._loaded_at
from {{ ref('stg_fhir__patients') }} p
left join {{ ref('stg_registry__tcga_pancan_patients') }} r on r.patient_barcode = p.patient_barcode
