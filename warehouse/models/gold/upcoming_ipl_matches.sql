{{ config(materialized='view') }}

-- Dashboard-facing view of upcoming or live IPL matches.
-- Excludes completed matches via status filter.

SELECT
    fixture_id,
    match_name,
    match_date,
    team_1,
    team_2,
    venue,
    status,
    series_name
FROM {{ ref('silver__fixtures') }}
WHERE is_ipl = TRUE
  AND (status IS NULL OR status NOT ILIKE '%won by%')
ORDER BY match_date
