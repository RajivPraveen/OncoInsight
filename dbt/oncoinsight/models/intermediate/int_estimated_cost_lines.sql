-- Reference-price micro-costing: applies CMS 2026 national payment rates (PFS, ASP, NADAC) to each delivered
-- treatment's observed utilisation (cycles, fractions, therapy days), falling back to standard regimen
-- defaults. These are ESTIMATES for comparing pathways, not actual charges or claims.
with ev as (
    select e.*, lower(trim(e.treatment_name)) as agent_key
    from {{ ref('int_treatment_events') }} e
    where e.is_delivered
),
prices as (select * from {{ ref('ref_cms_reference_prices') }}),
drug as (
    select
        ev.treatment_id, ev.patient_id, ev.pathway_modality, 'drug' as cost_component,
        cat.price_id,
        case cat.dosing_basis
            when 'daily' then least(greatest(coalesce(ev.end_day - ev.start_day, cat.default_administrations), 1), 3653)
            else least(coalesce(ev.number_of_cycles, cat.default_administrations), 36) * coalesce(cat.administrations_per_cycle, 1)
        end::numeric                                               as administrations,
        cat.units_per_administration,
        case
            when cat.dosing_basis = 'daily' and ev.end_day is not null and ev.start_day is not null then false
            when cat.dosing_basis <> 'daily' and ev.number_of_cycles is not null then false
            else true
        end                                                        as used_default_quantity,
        cat.dosing_assumption                                      as basis
    from ev
    join {{ ref('ref_agent_catalog') }} cat on cat.agent_key = ev.agent_key
    where cat.price_id is not null and ev.fhir_resource_type <> 'Procedure'
),
drug_lines as (
    select d.treatment_id, d.patient_id, d.pathway_modality, d.cost_component, d.price_id,
           d.administrations * d.units_per_administration as units, d.used_default_quantity, d.basis
    from drug d
),
-- chemo administration: concurrent same-day IV agents share one infusion per administration
infusion_groups as (
    select
        ev.patient_id,
        coalesce(ev.start_day::text, ev.treatment_id)              as regimen_key,
        min(ev.treatment_id)                                       as treatment_id,
        min(ev.pathway_modality)                                   as pathway_modality,
        max(least(coalesce(ev.number_of_cycles, cat.default_administrations), 36) * coalesce(cat.administrations_per_cycle, 1)) as infusions,
        bool_and(ev.number_of_cycles is null)                      as used_default_quantity
    from ev
    join {{ ref('ref_agent_catalog') }} cat on cat.agent_key = ev.agent_key
    where cat.iv_infusion and ev.fhir_resource_type <> 'Procedure'
    group by ev.patient_id, coalesce(ev.start_day::text, ev.treatment_id)
),
admin_lines as (
    select g.treatment_id, g.patient_id, g.pathway_modality, 'administration' as cost_component, r.price_id,
           g.infusions * r.quantity_multiplier as units, g.used_default_quantity, r.assumption as basis
    from infusion_groups g
    cross join {{ ref('ref_procedure_cost_rules') }} r
    where r.modality = 'chemo_admin'
),
radiation_lines as (
    select
        ev.treatment_id, ev.patient_id, ev.pathway_modality, 'radiation' as cost_component, r.price_id,
        (case r.quantity_basis
            when 'per_course' then 1
            when 'per_fraction' then least(greatest(coalesce(ev.number_of_fractions, {{ var('default_radiation_fractions') }}), 1), 60)
            when 'per_5_fractions' then ceil(least(greatest(coalesce(ev.number_of_fractions, {{ var('default_radiation_fractions') }}), 1), 60) / 5.0)
        end * r.quantity_multiplier)::numeric as units,
        ev.number_of_fractions is null and r.quantity_basis <> 'per_course' as used_default_quantity,
        r.assumption as basis
    from ev
    cross join {{ ref('ref_procedure_cost_rules') }} r
    where ev.pathway_modality = 'Radiation' and r.modality = 'radiation'
),
surgery_lines as (
    select
        ev.treatment_id, ev.patient_id, ev.pathway_modality, 'surgery' as cost_component, r.price_id,
        (case when ev.treatment_intent = 'Re-Excision'
              then case when r.rule_id = 'surg_lumpectomy' then 1 else 0 end
              else r.quantity_multiplier end)::numeric as units,
        false as used_default_quantity,
        r.assumption as basis
    from ev
    cross join {{ ref('ref_procedure_cost_rules') }} r
    where ev.pathway_modality = 'Surgery' and r.modality = 'surgery'
),
lines as (
    select * from drug_lines
    union all select * from admin_lines
    union all select * from radiation_lines
    union all select * from surgery_lines
)
select
    md5(l.treatment_id || '|' || l.cost_component || '|' || l.price_id) as cost_line_id,
    l.treatment_id,
    l.patient_id,
    l.pathway_modality,
    l.cost_component,
    l.price_id,
    p.hcpcs_code,
    p.description                                   as price_description,
    p.price_basis,
    round(l.units::numeric, 3)                      as units,
    p.unit_price_usd,
    round((l.units * p.unit_price_usd)::numeric, 2) as estimated_amount_usd,
    l.used_default_quantity,
    l.basis                                         as quantity_basis
from lines l
join prices p on p.price_id = l.price_id
where l.units > 0
