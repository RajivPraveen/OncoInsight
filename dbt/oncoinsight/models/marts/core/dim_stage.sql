select stage_group, stage_major, stage_order,
       case when stage_major in ('I', 'II') then 'Early (I-II)'
            when stage_major = 'III' then 'Locally advanced (III)'
            when stage_major = 'IV' then 'Metastatic (IV)'
            else 'Unknown' end as stage_category
from {{ ref('ref_ajcc_stage') }}
