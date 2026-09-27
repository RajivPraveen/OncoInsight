-- Hospital benchmarking of treatment timing vs the network. Only treating facilities with >= min n.
with d as (select * from {{ ref('mart_treatment_delay') }}),
network as (
    select interval_name, round((percentile_cont(0.5) within group (order by interval_days))::numeric, 1) as network_median_days
    from d group by interval_name
),
site as (
    select
        interval_name, hospital_id, hospital_name, site_type,
        count(*)                                                        as n_patients,
        round((percentile_cont(0.25) within group (order by interval_days))::numeric, 1)    as p25_days,
        round((percentile_cont(0.5) within group (order by interval_days))::numeric, 1)    as median_days,
        round((percentile_cont(0.75) within group (order by interval_days))::numeric, 1)    as p75_days,
        round((percentile_cont(0.9) within group (order by interval_days))::numeric, 1)    as p90_days,
        round(100.0 * avg(exceeds_threshold::int), 1)                  as pct_over_threshold
    from d
    where is_benchmarkable
    group by interval_name, hospital_id, hospital_name, site_type
)
select s.*, n.network_median_days,
       s.median_days - n.network_median_days                          as median_diff_vs_network_days,
       s.n_patients >= 10                                              as is_reportable
from site s join network n using (interval_name)
