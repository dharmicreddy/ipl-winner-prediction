{{ config(materialized='view') }}

-- Every delivery in every match, enriched with match and venue context.
-- Surrogate key delivery_id is generated from match + innings + over + ball.

SELECT
    {{ dbt_utils.generate_surrogate_key(['d.match_id', 'd.innings', 'd.over_number', 'd.ball_in_over']) }} AS delivery_id,
    d.match_id,
    m.season,
    m.match_date,
    m.venue,
    d.innings,
    d.over_number,
    d.ball_in_over,
    d.batting_team,
    d.bowling_team,
    d.batter,
    d.non_striker,
    d.bowler,
    d.runs_batter,
    d.runs_extras,
    d.runs_total,
    d.extras_type,
    d.wicket_kind,
    d.player_out
FROM {{ ref('silver__deliveries') }} d
INNER JOIN {{ ref('silver__matches') }} m ON d.match_id = m.match_id
WHERE m.winner IS NOT NULL
