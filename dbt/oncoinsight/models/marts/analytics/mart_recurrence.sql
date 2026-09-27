-- Recurrence / progression analysis set. Primary endpoint: PFI (PanCancer CDR progression-free interval),
-- which counts local recurrence, distant metastasis, new primary tumour or death with tumour.
select
    s.patient_id, s.pfs_months as time_to_event_months, s.pfs_event as recurrence_event,
    s.dfs_months, s.dfs_event,
    s.age_at_diagnosis, s.age_group, s.stage_major, s.t_category, s.n_category, s.lymph_nodes_positive,
    s.histology_group, s.receptor_subtype, s.pam50_subtype, s.er_status, s.her2_status,
    s.pathway_group, s.received_chemotherapy, s.received_radiation, s.received_endocrine,
    s.received_her2_targeted, s.chemo_delayed_over_90d, s.race_ethnicity, s.site_type,
    p.recurrence_type, p.days_to_recurrence, p.n_follow_up_visits, p.follow_up_visits_per_year
from {{ ref('mart_survival') }} s
join {{ ref('mart_patient_360') }} p on p.patient_id = s.patient_id
where s.pfs_months is not null and s.pfs_event is not null and s.stage_major <> 'IV'
