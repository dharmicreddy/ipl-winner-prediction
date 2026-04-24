{#
  Override dbt's default schema-naming behavior.

  By default, dbt concatenates <target.schema>_<+schema> like "dbt_build_silver".
  We want to use the +schema value directly so silver models land in `silver`
  and gold models land in `gold` — matching our Postgres layout exactly.

  If no +schema is configured, fall back to the target's default (dbt_build).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
