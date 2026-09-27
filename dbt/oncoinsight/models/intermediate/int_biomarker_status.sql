-- Resolve ER / PR / HER2 per patient following ASCO/CAP logic: an in-situ hybridization (FISH) result
-- is definitive for HER2 and overrides IHC; IHC equivocal (2+) without ISH remains Equivocal.
with b as (
    select patient_id, biomarker, upper(coalesce(method, '')) as method, value_text
    from {{ ref('stg_fhir__observations') }}
    where biomarker is not null
),
agg as (
    select
        patient_id,
        bool_or(biomarker = 'ER'   and value_text = 'Positive')  as er_pos,
        bool_or(biomarker = 'ER'   and value_text = 'Negative')  as er_neg,
        bool_or(biomarker = 'ER'   and value_text = 'Equivocal') as er_eq,
        bool_or(biomarker = 'PR'   and value_text = 'Positive')  as pr_pos,
        bool_or(biomarker = 'PR'   and value_text = 'Negative')  as pr_neg,
        bool_or(biomarker = 'PR'   and value_text = 'Equivocal') as pr_eq,
        bool_or(biomarker = 'HER2' and method like '%ISH%' and value_text = 'Positive') as her2_ish_pos,
        bool_or(biomarker = 'HER2' and method like '%ISH%' and value_text = 'Negative') as her2_ish_neg,
        bool_or(biomarker = 'HER2' and method = 'IHC' and value_text = 'Positive')  as her2_ihc_pos,
        bool_or(biomarker = 'HER2' and method = 'IHC' and value_text = 'Negative')  as her2_ihc_neg,
        bool_or(biomarker = 'HER2' and value_text = 'Equivocal')                    as her2_eq
    from b
    group by patient_id
),
resolved as (
    select
        patient_id,
        case when er_pos then 'Positive' when er_neg then 'Negative' when er_eq then 'Equivocal' else 'Unknown' end as er_status,
        case when pr_pos then 'Positive' when pr_neg then 'Negative' when pr_eq then 'Equivocal' else 'Unknown' end as pr_status,
        case when her2_ish_pos then 'Positive'
             when her2_ish_neg then 'Negative'
             when her2_ihc_pos then 'Positive'
             when her2_ihc_neg then 'Negative'
             when her2_eq then 'Equivocal'
             else 'Unknown' end as her2_status,
        (her2_ish_pos or her2_ish_neg) as her2_resolved_by_ish
    from agg
)
select
    p.patient_id,
    coalesce(r.er_status, 'Unknown')   as er_status,
    coalesce(r.pr_status, 'Unknown')   as pr_status,
    coalesce(r.her2_status, 'Unknown') as her2_status,
    coalesce(r.her2_resolved_by_ish, false) as her2_resolved_by_ish,
    case when r.er_status = 'Positive' or r.pr_status = 'Positive' then 'Positive'
         when r.er_status = 'Negative' and r.pr_status = 'Negative' then 'Negative'
         else 'Unknown' end as hr_status,
    case
        when (r.er_status = 'Positive' or r.pr_status = 'Positive') and r.her2_status = 'Negative' then 'HR+/HER2-'
        when (r.er_status = 'Positive' or r.pr_status = 'Positive') and r.her2_status = 'Positive' then 'HR+/HER2+'
        when r.er_status = 'Negative' and r.pr_status = 'Negative' and r.her2_status = 'Positive' then 'HR-/HER2+'
        when r.er_status = 'Negative' and r.pr_status = 'Negative' and r.her2_status = 'Negative' then 'Triple negative'
        else 'Unknown'
    end as receptor_subtype
from {{ ref('stg_fhir__patients') }} p
left join resolved r on r.patient_id = p.patient_id
