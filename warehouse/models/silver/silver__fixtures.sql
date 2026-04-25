{{ config(materialized='view') }}

SELECT
    fixture_id,
    match_name,
    match_type,
    status,
    venue,
    match_date,
    series_name,
    team_1,
    team_2,
    is_ipl,
    raw_response_id,
    parsed_at
FROM {{ source('silver_raw', 'fixtures') }}
