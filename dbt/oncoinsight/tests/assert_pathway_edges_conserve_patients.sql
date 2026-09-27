-- Every patient contributes exactly one edge out of the Diagnosis node in the Sankey.
select d.n_from_diagnosis, p.n_patients
from (select sum(n_patients) as n_from_diagnosis from {{ ref('mart_pathway_transitions') }} where source = 'Diagnosis') d
cross join (select count(*) as n_patients from {{ ref('mart_patient_360') }}) p
where d.n_from_diagnosis <> p.n_patients
