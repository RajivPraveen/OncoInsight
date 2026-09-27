-- Every raw FHIR patient that is not soft-deleted must reach the Patient 360 mart.
select r.id from {{ source('fhir', 'fhir_patient') }} r
left join {{ ref('mart_patient_360') }} p on p.patient_id = r.id
where not r._is_deleted and p.patient_id is null
