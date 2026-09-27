select
    d.condition_id                            as diagnosis_id,
    d.patient_id,
    p.hospital_id,
    d.anchored_diagnosis_date,
    d.year_of_diagnosis,
    md5(coalesce(d.morphology_code, 'NA') || '|' || coalesce(d.icd10_code, 'NA')) as cancer_key,
    md5(b.er_status || '|' || b.pr_status || '|' || b.her2_status)                 as biomarker_key,
    d.stage_group,
    d.stage_major,
    d.t_category,
    d.n_category,
    d.m_category,
    d.lymph_nodes_positive,
    d.lymph_nodes_examined,
    d.laterality,
    d.method_of_diagnosis,
    b.receptor_subtype,
    r.pam50_subtype
from {{ ref('int_primary_diagnosis') }} d
join {{ ref('stg_fhir__patients') }} p on p.patient_id = d.patient_id
left join {{ ref('int_biomarker_status') }} b on b.patient_id = d.patient_id
left join {{ ref('stg_registry__tcga_pancan_patients') }} r on r.patient_barcode = p.patient_barcode
