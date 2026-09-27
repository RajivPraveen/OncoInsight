select
    o.id                                        as hospital_id,
    o.tss_code,
    trim(o.name)                                as hospital_name,
    o.bcr_id,
    coalesce(c.site_type, 'Unclassified')       as site_type,
    coalesce(c.is_treating_facility, true)      as is_treating_facility,
    o._loaded_at
from {{ source('fhir', 'fhir_organization') }} o
left join {{ ref('ref_site_classification') }} c on c.tss_code = o.tss_code
where not o._is_deleted
