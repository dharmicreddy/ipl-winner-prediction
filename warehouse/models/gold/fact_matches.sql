{{ config(materialized='view') }}

-- One row per IPL match with derived analytical columns.
-- Resolves team rebrandings via team_canonical seed so analyses stay
-- consistent across seasons.

WITH matches_with_canonicals AS (
    SELECT
        m.match_id,
        m.season,
        m.match_date,
        m.venue,
        m.city,
        th.team_canonical AS team_home,
        ta.team_canonical AS team_away,
        tt.team_canonical AS toss_winner,
        m.toss_decision,
        tw.team_canonical AS winner,
        m.win_margin_type,
        m.win_margin,
        m.method
    FROM {{ ref('silver__matches') }} m
    LEFT JOIN {{ ref('team_canonical') }} th ON m.team_home = th.team_variant
    LEFT JOIN {{ ref('team_canonical') }} ta ON m.team_away = ta.team_variant
    LEFT JOIN {{ ref('team_canonical') }} tt ON m.toss_winner = tt.team_variant
    LEFT JOIN {{ ref('team_canonical') }} tw ON m.winner = tw.team_variant
    WHERE m.winner IS NOT NULL  -- exclude no-result matches
)
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
    -- Derived: which team batted first?
    CASE
        WHEN toss_decision = 'bat' THEN toss_winner
        WHEN toss_winner = team_home THEN team_away
        ELSE team_home
    END AS batting_first,
    -- Derived: did the team that batted first win?
    CASE
        WHEN toss_decision = 'bat' THEN toss_winner
        WHEN toss_winner = team_home THEN team_away
        ELSE team_home
    END = winner AS batting_first_won
FROM matches_with_canonicals
ORDER BY match_date
