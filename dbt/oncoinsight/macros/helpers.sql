{# Cast free-text registry values to numeric, returning null for "[Not Available]" style tokens. #}
{% macro safe_numeric(col) -%}
    case when trim({{ col }}) ~ '^-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?$' then trim({{ col }})::numeric end
{%- endmacro %}

{# cBioPortal survival status fields look like "1:DECEASED" / "0:LIVING". #}
{% macro status_event(col) -%}
    case when {{ col }} like '1:%' then 1 when {{ col }} like '0:%' then 0 end
{%- endmacro %}

{# AJCC stage group -> major stage (0, I, II, III, IV) #}
{% macro stage_major(col) -%}
    case
        when {{ col }} ~* '^stage iv' then 'IV'
        when {{ col }} ~* '^stage iii' then 'III'
        when {{ col }} ~* '^stage ii' then 'II'
        when {{ col }} ~* '^stage i' then 'I'
        when {{ col }} ~* '^stage 0' then '0'
        else 'Unknown'
    end
{%- endmacro %}

{% macro age_group(col) -%}
    case
        when {{ col }} is null then 'Unknown'
        when {{ col }} < 40 then '<40'
        when {{ col }} < 50 then '40-49'
        when {{ col }} < 65 then '50-64'
        when {{ col }} < 75 then '65-74'
        else '75+'
    end
{%- endmacro %}

{# Incremental filter on the warehouse load timestamp #}
{% macro incremental_loaded_at(source_col='_loaded_at', target_col='_loaded_at') -%}
    {% if is_incremental() %}
    where {{ source_col }} > (select coalesce(max(t.{{ target_col }}), '1900-01-01'::timestamptz) from {{ this }} t)
    {% endif %}
{%- endmacro %}

{# Grant the read-only BI/API role usage on curated schemas (idempotent; skips missing schemas/role). #}
{% macro grant_reader_usage(schemas=['core', 'marts', 'ref']) %}
    {% set reader = env_var('WAREHOUSE_READER_USER', 'onco_reader') %}
    do $$
    declare s text;
    begin
        if exists (select 1 from pg_roles where rolname = '{{ reader }}') then
            foreach s in array array[{% for s in schemas %}'{{ s }}'{% if not loop.last %}, {% endif %}{% endfor %}] loop
                if exists (select 1 from information_schema.schemata where schema_name = s) then
                    execute format('grant usage on schema %I to %I', s, '{{ reader }}');
                    execute format('grant select on all tables in schema %I to %I', s, '{{ reader }}');
                end if;
            end loop;
        end if;
    end $$;
{% endmacro %}
