{{ config(materialized='view') }}

-- For each match, compute the historical head-to-head record between the
-- two teams (strictly before this match's date). See ADR-007.

SELECT
    m.match_id,
    m.match_date,
    m.team_home,
    m.team_away,
    -- Count of prior matches between these two teams (in either home/away role)
    (
        SELECT COUNT(*)
        FROM {{ ref('fact_matches') }} h
        WHERE (
            (h.team_home = m.team_home AND h.team_away = m.team_away)
            OR (h.team_home = m.team_away AND h.team_away = m.team_home)
        )
        AND h.match_date < m.match_date
    ) AS h2h_matches_played,
    -- Wins by team_home in those prior matches
    (
        SELECT COUNT(*)
        FROM {{ ref('fact_matches') }} h
        WHERE (
            (h.team_home = m.team_home AND h.team_away = m.team_away)
            OR (h.team_home = m.team_away AND h.team_away = m.team_home)
        )
        AND h.winner = m.team_home
        AND h.match_date < m.match_date
    ) AS team_home_h2h_wins,
    -- Win rate (NULL when no prior matches)
    (
        SELECT
            CASE
                WHEN COUNT(*) = 0 THEN NULL
                ELSE 1.0 * SUM(CASE WHEN h.winner = m.team_home THEN 1 ELSE 0 END) / COUNT(*)
            END
        FROM {{ ref('fact_matches') }} h
        WHERE (
            (h.team_home = m.team_home AND h.team_away = m.team_away)
            OR (h.team_home = m.team_away AND h.team_away = m.team_home)
        )
        AND h.match_date < m.match_date
    ) AS team_home_h2h_win_rate
FROM {{ ref('fact_matches') }} m
ORDER BY m.match_date
