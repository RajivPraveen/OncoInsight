-- Patient-level cost must equal the sum of its cost lines (to the cent).
with lines as (select patient_id, sum(estimated_amount_usd) as total from {{ ref('fact_estimated_cost') }} group by 1)
select p.patient_id, p.total_estimated_cost_usd, l.total
from {{ ref('mart_patient_360') }} p
join lines l using (patient_id)
where abs(p.total_estimated_cost_usd - l.total) > 0.01
