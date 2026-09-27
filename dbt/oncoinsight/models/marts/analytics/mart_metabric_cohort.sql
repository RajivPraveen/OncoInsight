-- METABRIC validation cohort (n=2,509): cleaned clinical, receptor subtype and treatment-combination fields.
select
    m.patient_id,
    m.age_at_diagnosis,
    {{ age_group('m.age_at_diagnosis') }}                          as age_group,
    m.cohort,
    m.tumor_size_mm,
    m.tumor_grade,
    coalesce(m.tumor_stage::text, 'Unknown')                        as tumor_stage,
    m.lymph_nodes_positive,
    m.nottingham_prognostic_index,
    m.pam50_claudin_subtype,
    m.er_status, m.pr_status, m.her2_status,
    case
        when (m.er_status = 'Positive' or m.pr_status = 'Positive') and m.her2_status = 'Negative' then 'HR+/HER2-'
        when (m.er_status = 'Positive' or m.pr_status = 'Positive') and m.her2_status = 'Positive' then 'HR+/HER2+'
        when m.er_status = 'Negative' and m.pr_status = 'Negative' and m.her2_status = 'Positive' then 'HR-/HER2+'
        when m.er_status = 'Negative' and m.pr_status = 'Negative' and m.her2_status = 'Negative' then 'Triple negative'
        else 'Unknown'
    end                                                             as receptor_subtype,
    m.menopausal_state,
    m.breast_surgery,
    m.received_chemotherapy, m.received_hormone_therapy, m.received_radiotherapy,
    concat_ws(' + ',
        case when m.breast_surgery = 'MASTECTOMY' then 'Mastectomy' when m.breast_surgery = 'BREAST CONSERVING' then 'BCS' end,
        case when m.received_chemotherapy then 'Chemo' end,
        case when m.received_radiotherapy then 'RT' end,
        case when m.received_hormone_therapy then 'Endocrine' end)  as treatment_combination,
    m.os_months, m.os_event, m.dss_event, m.rfs_months, m.rfs_event, m.vital_status
from {{ ref('stg_registry__metabric_patients') }} m
