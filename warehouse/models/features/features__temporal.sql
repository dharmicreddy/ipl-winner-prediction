{{ config(materialized='view') }}

-- For each match, compute temporal features as-of match date.
-- See ADR-007 for leakage policy.

WITH match_with_priors AS (
    SELECT
        m.match_id,
        m.match_date,
        m.season,
        m.team_home,
        m.team_away,
        -- Last prior match date for each team
        (
            SELECT MAX(h.match_date)
            FROM {{ ref('fact_matches') }} h
            WHERE (h.team_home = m.team_home OR h.team_away = m.team_home)
              AND h.match_date < m.match_date
        ) AS team_home_last_match_date,
        (
            SELECT MAX(h.match_date)
            FROM {{ ref('fact_matches') }} h
            WHERE (h.team_home = m.team_away OR h.team_away = m.team_away)
              AND h.match_date < m.match_date
        ) AS team_away_last_match_date,
        -- Match number within the current season (1-indexed by date)
        (
            SELECT COUNT(*)
            FROM {{ ref('fact_matches') }} h
            WHERE h.season = m.season
              AND h.match_date < m.match_date
        ) + 1 AS match_number_in_season
    FROM {{ ref('fact_matches') }} m
)
SELECT
    match_id,
    match_date,
    -- Days since each team's last match (NULL for first match of dataset/season)
    CASE
        WHEN team_home_last_match_date IS NULL THEN NULL
        ELSE EXTRACT(DAY FROM (match_date::timestamp - team_home_last_match_date::timestamp))::int
    END AS days_since_team_home_last_match,
    CASE
        WHEN team_away_last_match_date IS NULL THEN NULL
        ELSE EXTRACT(DAY FROM (match_date::timestamp - team_away_last_match_date::timestamp))::int
    END AS days_since_team_away_last_match,
    match_number_in_season
FROM match_with_priors
ORDER BY match_date
