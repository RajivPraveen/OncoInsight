-- Patient-level outcomes. Survival endpoints come from the TCGA PanCancer Clinical Data Resource
-- (recommended curated endpoints); GDC vital status / follow-up are used as fallback.
select
    p.patient_id,
    p.patient_barcode,
    coalesce(r.os_months, round(greatest(f.last_contact_day, 0) / 30.4375, 2)) as os_months,
    coalesce(r.os_event, case when p.vital_status = 'Dead' then 1 when p.vital_status = 'Alive' then 0 end) as os_event,
    r.dss_months, r.dss_event,
    r.pfs_months, r.pfs_event,
    r.dfs_months, r.dfs_event,
    (r.os_months is not null)                              as endpoints_from_pancan_cdr,
    p.vital_status,
    f.last_contact_day,
    f.n_follow_up_visits,
    f.last_disease_status,
    f.gdc_recurrence_recorded,
    f.first_recurrence_day,
    f.recurrence_type,
    f.recurrence_site,
    coalesce(r.pfs_event = 1, false) or f.gdc_recurrence_recorded as any_progression_or_recurrence,
    r.new_tumor_event,
    r.cancer_status
from {{ ref('stg_fhir__patients') }} p
left join {{ ref('stg_registry__tcga_pancan_patients') }} r on r.patient_barcode = p.patient_barcode
left join {{ ref('int_follow_up') }} f on f.patient_id = p.patient_id
