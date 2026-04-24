{{ config(materialized='view') }}

SELECT
    match_id,
    innings,
    over_number,
    ball_in_over,
    batting_team,
    bowling_team,
    batter,
    non_striker,
    bowler,
    runs_batter,
    runs_extras,
    runs_total,
    extras_type,
    wicket_kind,
    player_out
FROM {{ source('silver_raw', 'deliveries') }}
