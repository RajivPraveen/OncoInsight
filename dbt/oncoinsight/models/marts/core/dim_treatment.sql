-- Treatment catalogue: normalised systemic agents plus procedure-based modalities.
select distinct on (canonical_agent)
    md5('agent|' || canonical_agent) as treatment_key, canonical_agent as treatment_name, drug_class,
    pathway_modality, route, price_id is not null as is_priced, dosing_assumption
from {{ ref('ref_agent_catalog') }}
union all
select md5('proc|Surgery'), 'Breast surgery', 'Surgery', 'Surgery', 'Procedure', true,
       'Blended lumpectomy/mastectomy surgeon fee + axillary staging'
union all
select md5('proc|Radiation'), 'Radiation therapy', 'Radiation therapy', 'Radiation', 'Procedure', true,
       'Planning + per-fraction delivery + weekly management'
