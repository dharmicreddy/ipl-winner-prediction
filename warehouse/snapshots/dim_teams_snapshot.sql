{% snapshot dim_teams_snapshot %}

{{
    config(
      target_schema='snapshots',
      strategy='check',
      unique_key='team_canonical',
      check_cols=['team_short_name'],
    )
}}

SELECT
    team_canonical,
    team_short_name
FROM {{ ref('dim_teams') }}

{% endsnapshot %}
