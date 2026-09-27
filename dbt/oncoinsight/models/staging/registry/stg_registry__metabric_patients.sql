-- METABRIC: patient attributes joined to the (single) primary tumour sample per patient.
with s as (
    select distinct on (patient_id) *
    from {{ source('registry', 'cbio_brca_metabric_sample') }}
    where not _is_deleted
    order by patient_id, sample_id
)
select
    p.patient_id,
    {{ safe_numeric('p.age_at_diagnosis') }}                     as age_at_diagnosis,
    p.cohort                                                     as cohort,
    p.breast_surgery                                             as breast_surgery,
    p.chemotherapy = 'YES'                                       as received_chemotherapy,
    p.hormone_therapy = 'YES'                                    as received_hormone_therapy,
    p.radio_therapy = 'YES'                                      as received_radiotherapy,
    p.claudin_subtype                                            as pam50_claudin_subtype,
    p.inferred_menopausal_state                                  as menopausal_state,
    p.er_ihc                                                     as er_ihc,
    p.her2_snp6                                                  as her2_snp6,
    {{ safe_numeric('p.lymph_nodes_examined_positive') }}::int   as lymph_nodes_positive,
    {{ safe_numeric('p.npi') }}                                  as nottingham_prognostic_index,
    p.histological_subtype,
    p.cellularity,
    p.laterality,
    {{ safe_numeric('p.os_months') }}                            as os_months,
    {{ status_event('p.os_status') }}                            as os_event,
    p.vital_status,
    case when p.vital_status = 'Died of Disease' then 1
         when p.vital_status in ('Living', 'Died of Other Causes') then 0 end as dss_event,
    {{ safe_numeric('p.rfs_months') }}                           as rfs_months,
    {{ status_event('p.rfs_status') }}                           as rfs_event,
    s.er_status,
    s.pr_status,
    s.her2_status,
    {{ safe_numeric('s.grade') }}::int                           as tumor_grade,
    {{ safe_numeric('s.tumor_size') }}                           as tumor_size_mm,
    {{ safe_numeric('s.tumor_stage') }}::int                     as tumor_stage,
    {{ safe_numeric('s.tmb_nonsynonymous') }}                    as tmb_nonsynonymous,
    greatest(p._loaded_at, s._loaded_at)                         as _loaded_at
from {{ source('registry', 'cbio_brca_metabric_patient') }} p
left join s on s.patient_id = p.patient_id
where not p._is_deleted
