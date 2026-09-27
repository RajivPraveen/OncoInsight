-- Unified treatment timeline (surgery, radiation, systemic therapy) for the index primary cancer, with
-- agent normalisation through ref_agent_catalog. Day offsets are relative to the index diagnosis date.
with primary_conditions as (
    select condition_id from {{ ref('stg_fhir__conditions') }} where is_primary
),
procedures as (
    select
        p.treatment_id, p.fhir_resource_type, p.patient_id, p.condition_id, p.status, p.is_delivered,
        case when p.source_modality = 'surgery' then 'Surgery' else 'Radiation' end as pathway_modality,
        p.treatment_type                               as treatment_name,
        null::text                                     as canonical_agent,
        case when p.source_modality = 'surgery' then 'Surgery' else 'Radiation therapy' end as drug_class,
        p.days_to_treatment_start, p.days_to_treatment_end,
        p.treatment_intent, p.treatment_outcome, p.number_of_cycles, p.number_of_fractions,
        p.delivered_dose_cgy, p.margin_status, p.hospital_id, p._loaded_at
    from {{ ref('stg_fhir__procedures') }} p
),
medications as (
    select
        m.treatment_id, m.fhir_resource_type, m.patient_id, m.condition_id, m.status, m.is_delivered,
        coalesce(cat.pathway_modality,
            case m.source_modality
                when 'chemotherapy' then 'Chemotherapy'
                when 'hormone_therapy' then 'Endocrine'
                when 'targeted_therapy' then 'Other targeted'
                when 'immunotherapy' then 'Immunotherapy'
                when 'bisphosphonate' then 'Bone-modifying'
                when 'ancillary' then 'Supportive'
                else 'Unspecified systemic' end)       as pathway_modality,
        m.agent_raw                                    as treatment_name,
        coalesce(cat.canonical_agent, m.agent_raw)     as canonical_agent,
        coalesce(cat.drug_class, 'Unclassified')       as drug_class,
        m.days_to_treatment_start, m.days_to_treatment_end,
        m.treatment_intent, m.treatment_outcome, m.number_of_cycles, null::bigint as number_of_fractions,
        null::double precision as delivered_dose_cgy, null::text as margin_status, m.hospital_id, m._loaded_at
    from {{ ref('stg_fhir__medications') }} m
    left join {{ ref('ref_agent_catalog') }} cat on cat.agent_key = m.agent_key
),
unioned as (
    select * from procedures
    union all
    select * from medications
)
select
    u.*,
    -- TCGA's index date is the initial pathologic diagnosis, which for resected breast cancer is the
    -- surgical specimen date; undated delivered surgeries are therefore placed at day 0 (flagged).
    case when u.pathway_modality = 'Surgery' and u.days_to_treatment_start is null and u.is_delivered
         then 0 else u.days_to_treatment_start end                             as start_day,
    (u.pathway_modality = 'Surgery' and u.days_to_treatment_start is null and u.is_delivered) as start_day_imputed,
    u.days_to_treatment_end                                                    as end_day,
    case
        when u.pathway_modality in ('Surgery', 'Chemotherapy', 'Radiation', 'Endocrine', 'HER2-targeted') then u.pathway_modality
        when u.pathway_modality in ('Other targeted', 'Immunotherapy', 'Unspecified systemic') then 'Other systemic'
    end                                                                        as pathway_group
from unioned u
join primary_conditions pc on pc.condition_id = u.condition_id
