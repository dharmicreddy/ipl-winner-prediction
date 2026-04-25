{{ config(materialized='view') }}

-- One row per canonical team. Resolves rebrandings using the seed.
-- Source teams come from silver__matches (home + away unioned).

WITH all_teams AS (
    SELECT team_home AS team_variant FROM {{ ref('silver__matches') }}
    UNION
    SELECT team_away AS team_variant FROM {{ ref('silver__matches') }}
),
joined AS (
    SELECT
        t.team_variant,
        c.team_canonical,
        c.team_short_name
    FROM all_teams t
    LEFT JOIN {{ ref('team_canonical') }} c
        ON t.team_variant = c.team_variant
)
SELECT DISTINCT
    team_canonical,
    team_short_name
FROM joined
WHERE team_canonical IS NOT NULL
ORDER BY team_canonical
