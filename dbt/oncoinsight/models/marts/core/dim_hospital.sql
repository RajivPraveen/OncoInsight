-- TCGA tissue source sites. Biorepositories procure tissue but do not treat patients, so hospital
-- benchmarking filters on is_treating_facility and a minimum patient count.
with volume as (
    select hospital_id, count(*) as n_patients from {{ ref('stg_fhir__patients') }} group by 1
)
select
    o.hospital_id,
    o.tss_code,
    o.hospital_name,
    o.site_type,
    o.is_treating_facility,
    coalesce(v.n_patients, 0)                                  as n_patients,
    case when coalesce(v.n_patients, 0) >= 60 then 'High (60+)'
         when coalesce(v.n_patients, 0) >= {{ var('min_hospital_patients') }} then 'Medium (20-59)'
         else 'Low (<20)' end                                  as volume_tier,
    coalesce(v.n_patients, 0) >= {{ var('min_hospital_patients') }} and o.is_treating_facility as is_benchmarkable
from {{ ref('stg_fhir__organizations') }} o
left join volume v on v.hospital_id = o.hospital_id
