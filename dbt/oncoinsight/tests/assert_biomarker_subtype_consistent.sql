-- A triple-negative label must never co-exist with any positive receptor.
select * from {{ ref('int_biomarker_status') }}
where receptor_subtype = 'Triple negative'
  and (er_status = 'Positive' or pr_status = 'Positive' or her2_status = 'Positive')
