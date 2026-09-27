-- Estimated cost lines ("reference-priced claims"). See int_estimated_cost_lines for method.
select l.*, e.condition_id as diagnosis_id, e.hospital_id, e.start_day
from {{ ref('int_estimated_cost_lines') }} l
join {{ ref('int_treatment_events') }} e on e.treatment_id = l.treatment_id
