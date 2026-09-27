{# Generic tests (kept in-repo instead of depending on dbt_utils so builds work offline). #}

{% test expression_is_true(model, expression, where=none) %}
select * from {{ model }}
where not ({{ expression }})
{% if where %} and {{ where }} {% endif %}
{% endtest %}

{% test non_negative(model, column_name) %}
select * from {{ model }} where {{ column_name }} < 0
{% endtest %}

{% test within_range(model, column_name, min_value, max_value) %}
select * from {{ model }}
where {{ column_name }} is not null and ({{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }})
{% endtest %}

{% test row_count_between(model, min_value, max_value) %}
select n from (select count(*) as n from {{ model }}) c
where n < {{ min_value }} or n > {{ max_value }}
{% endtest %}
