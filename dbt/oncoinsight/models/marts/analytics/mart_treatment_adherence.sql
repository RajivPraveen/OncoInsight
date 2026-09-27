-- Treatment completion signals available in TCGA: reported cycles vs the standard regimen length,
-- observed endocrine therapy duration vs 5 years, and the reported treatment outcome.
with t as (
    select f.*, cat.default_administrations, cat.dosing_basis
    from {{ ref('fact_treatment') }} f
    left join (
        select distinct on (canonical_agent) canonical_agent, default_administrations, dosing_basis
        from {{ ref('ref_agent_catalog') }} order by canonical_agent, agent_key
    ) cat on cat.canonical_agent = f.treatment_name
    where f.is_delivered and f.pathway_modality in ('Chemotherapy', 'HER2-targeted', 'Endocrine', 'Radiation')
)
select
    t.treatment_id, t.patient_id, t.pathway_modality, t.treatment_name, t.drug_class,
    t.number_of_cycles, t.default_administrations as standard_cycles,
    case when t.dosing_basis = 'per_cycle' and t.number_of_cycles is not null and t.default_administrations is not null
         then t.number_of_cycles >= t.default_administrations end                  as completed_standard_cycles,
    t.duration_days,
    case when t.pathway_modality = 'Endocrine' and t.duration_days is not null
         then t.duration_days >= 1644 end                                          as endocrine_4_5y_or_more,
    t.number_of_fractions,
    t.treatment_outcome,
    t.treatment_outcome in ('Progressive Disease')                                 as progressed_on_treatment,
    p.hospital_name, p.stage_major, p.receptor_subtype, p.age_group, p.race_ethnicity, p.os_event,
    p.any_progression_or_recurrence
from t
join {{ ref('mart_patient_360') }} p on p.patient_id = t.patient_id
