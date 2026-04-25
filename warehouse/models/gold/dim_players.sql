{{ config(materialized='view') }}

-- One row per distinct player who appeared in any match.
-- Counts derived from silver__deliveries: appearances as batter,
-- non-striker, bowler. A player typically appears as multiple roles.

WITH batters AS (
    SELECT DISTINCT batter AS player_name FROM {{ ref('silver__deliveries') }}
),
non_strikers AS (
    SELECT DISTINCT non_striker AS player_name FROM {{ ref('silver__deliveries') }}
),
bowlers AS (
    SELECT DISTINCT bowler AS player_name FROM {{ ref('silver__deliveries') }}
),
all_players AS (
    SELECT player_name FROM batters
    UNION
    SELECT player_name FROM non_strikers
    UNION
    SELECT player_name FROM bowlers
)
SELECT
    p.player_name,
    (SELECT COUNT(DISTINCT match_id) FROM {{ ref('silver__deliveries') }} d WHERE d.batter = p.player_name OR d.non_striker = p.player_name) AS matches_batted,
    (SELECT COUNT(DISTINCT match_id) FROM {{ ref('silver__deliveries') }} d WHERE d.bowler = p.player_name) AS matches_bowled,
    (SELECT COUNT(*) FROM {{ ref('silver__deliveries') }} d WHERE d.batter = p.player_name) AS balls_faced,
    (SELECT COUNT(*) FROM {{ ref('silver__deliveries') }} d WHERE d.bowler = p.player_name) AS balls_bowled
FROM all_players p
ORDER BY p.player_name
