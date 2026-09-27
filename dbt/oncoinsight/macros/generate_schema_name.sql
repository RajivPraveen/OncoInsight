{# Use the configured custom schema name verbatim (stg, int, core, marts, ref) rather than
   dbt's default "<target_schema>_<custom>" so BI tools see stable schema names. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}
