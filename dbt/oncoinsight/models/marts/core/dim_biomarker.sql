select distinct
    md5(er_status || '|' || pr_status || '|' || her2_status) as biomarker_key,
    er_status, pr_status, her2_status, hr_status, receptor_subtype
from {{ ref('int_biomarker_status') }}
