-- Analysis-ready survival dataset (TCGA-BRCA; PanCancer CDR endpoints) consumed by lifelines models.
with p as (select * from {{ ref('mart_patient_360') }}),
top_pathways as (
    select pathway from p group by pathway having count(*) >= 30
)
select
    p.patient_id, p.patient_barcode,
    p.os_months, p.os_event, p.dss_months, p.dss_event, p.pfs_months, p.pfs_event, p.dfs_months, p.dfs_event,
    p.age_at_diagnosis, p.age_group, p.stage_major, p.stage_category, p.t_category, p.n_category,
    p.lymph_nodes_positive, p.histology_group, p.receptor_subtype, p.pam50_subtype, p.er_status, p.her2_status,
    p.race, p.race_ethnicity, p.site_type, p.volume_tier, p.hospital_name, p.is_benchmarkable,
    case when tp.pathway is not null then p.pathway else 'Other' end as pathway_group,
    p.received_chemotherapy, p.received_radiation, p.received_endocrine, p.received_her2_targeted,
    p.days_to_chemotherapy, p.chemo_timing_group, p.chemo_delayed_over_90d, p.year_of_diagnosis
from p
left join top_pathways tp on tp.pathway = p.pathway
where p.os_months is not null and p.os_months >= 0 and p.os_event is not null
