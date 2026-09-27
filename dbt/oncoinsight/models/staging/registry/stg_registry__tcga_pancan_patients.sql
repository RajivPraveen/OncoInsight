-- TCGA PanCancer Atlas curated survival endpoints (TCGA Clinical Data Resource). Months -> days uses 30.4375.
select
    patient_id                                                   as patient_barcode,
    {{ safe_numeric('age') }}::int                               as age_at_diagnosis,
    nullif(subtype, '')                                          as pam50_subtype_raw,
    replace(subtype, 'BRCA_', '')                                as pam50_subtype,
    ajcc_pathologic_tumor_stage                                  as ajcc_stage,
    radiation_therapy,
    history_neoadjuvant_trtyn                                    as neoadjuvant_history,
    new_tumor_event_after_initial_treatment                      as new_tumor_event,
    person_neoplasm_cancer_status                                as cancer_status,
    race,
    ethnicity,
    genetic_ancestry_label,
    {{ safe_numeric('os_months') }}                              as os_months,
    {{ status_event('os_status') }}                              as os_event,
    {{ safe_numeric('dss_months') }}                             as dss_months,
    {{ status_event('dss_status') }}                             as dss_event,
    {{ safe_numeric('pfs_months') }}                             as pfs_months,
    {{ status_event('pfs_status') }}                             as pfs_event,
    {{ safe_numeric('dfs_months') }}                             as dfs_months,
    {{ status_event('dfs_status') }}                             as dfs_event,
    {{ safe_numeric('days_last_followup') }}::int                as days_last_followup,
    {{ safe_numeric('buffa_hypoxia_score') }}                    as buffa_hypoxia_score,
    _loaded_at
from {{ source('registry', 'cbio_brca_tcga_pan_can_atlas_2018_patient') }}
where not _is_deleted
