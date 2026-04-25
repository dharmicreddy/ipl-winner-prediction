{{ config(materialized='view') }}

-- For each match, compute historical venue-specific win rates as-of match
-- date. Uses raw venue string from fact_matches (not yet canonicalized to
-- a wiki_title — that join can be added later if needed).
-- See ADR-007 for leakage policy.

SELECT
    m.match_id,
    m.match_date,
    m.venue,
    -- Total matches played at this venue before today
    (
        SELECT COUNT(*)
        FROM {{ ref('fact_matches') }} h
        WHERE h.venue = m.venue
          AND h.match_date < m.match_date
    ) AS venue_matches_played,
    -- Bat-first win rate at this venue (NULL if no prior matches)
    (
        SELECT
            CASE
                WHEN COUNT(*) = 0 THEN NULL
                ELSE 1.0 * SUM(CASE WHEN h.batting_first_won THEN 1 ELSE 0 END) / COUNT(*)
            END
        FROM {{ ref('fact_matches') }} h
        WHERE h.venue = m.venue
          AND h.match_date < m.match_date
    ) AS venue_bat_first_win_rate
FROM {{ ref('fact_matches') }} m
ORDER BY m.match_date
