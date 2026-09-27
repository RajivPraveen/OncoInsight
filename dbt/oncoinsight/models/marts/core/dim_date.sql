select
    d::date                                   as date_day,
    extract(year from d)::int                 as year,
    extract(quarter from d)::int              as quarter,
    extract(month from d)::int                as month,
    to_char(d, 'YYYY-MM')                     as year_month,
    to_char(d, 'YYYY') || '-Q' || extract(quarter from d)::int as year_quarter,
    extract(isodow from d)::int               as iso_day_of_week
from generate_series('1985-01-01'::date, '2035-12-31'::date, interval '1 day') d
