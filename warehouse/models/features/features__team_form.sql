{{ config(materialized='view') }}

-- For each match, compute each team's win rate over their last 5 matches
-- (strictly before this match's date). The strictly-less-than predicate
-- is the leakage guard. See ADR-007.

SELECT
    m.match_id,
    m.match_date,
    m.team_home,
    m.team_away,
    -- Team home: win rate over last 5 prior matches
    (
        SELECT AVG(CASE WHEN h.winner = m.team_home THEN 1.0 ELSE 0.0 END)
        FROM (
            SELECT winner, match_date
            FROM {{ ref('fact_matches') }}
            WHERE (team_home = m.team_home OR team_away = m.team_home)
              AND match_date < m.match_date
            ORDER BY match_date DESC
            LIMIT 5
        ) h
    ) AS team_home_form_5,
    -- Team away: same pattern
    (
        SELECT AVG(CASE WHEN h.winner = m.team_away THEN 1.0 ELSE 0.0 END)
        FROM (
            SELECT winner, match_date
            FROM {{ ref('fact_matches') }}
            WHERE (team_home = m.team_away OR team_away = m.team_away)
              AND match_date < m.match_date
            ORDER BY match_date DESC
            LIMIT 5
        ) h
    ) AS team_away_form_5
FROM {{ ref('fact_matches') }} m
ORDER BY m.match_date
