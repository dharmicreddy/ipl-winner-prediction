{{ config(materialized='view') }}

SELECT
    match_id,
    season,
    match_date,
    venue,
    city,
    team_home,
    team_away,
    toss_winner,
    toss_decision,
    winner,
    win_margin_type,
    win_margin,
    method,
    player_of_match,
    officials,
    raw_ingested_at,
    parsed_at
FROM {{ source('silver_raw', 'matches') }}
