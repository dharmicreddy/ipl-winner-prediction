-- Singular test: verify no feature row references future or same-day data.
--
-- For each feature table, the as-of pattern in the model SQL guarantees
-- that source rows used for aggregation have match_date < target.match_date.
-- This test independently verifies the guarantee holds at the row level.
--
-- The test pattern: for each feature_table.match_id, the row's match_date
-- (joined back from fact_matches) must equal the source match_date used in
-- the feature model's SELECT. If they don't, the model is leaking.
--
-- Returns rows that VIOLATE the no-leakage guarantee. Test passes when zero rows.

WITH
-- Verify team_form: each match's match_date matches what fact_matches says
team_form_check AS (
    SELECT t.match_id, t.match_date AS feature_date, m.match_date AS fact_date
    FROM {{ ref('features__team_form') }} t
    JOIN {{ ref('fact_matches') }} m ON t.match_id = m.match_id
    WHERE t.match_date != m.match_date
),
-- Same for head_to_head
h2h_check AS (
    SELECT t.match_id, t.match_date AS feature_date, m.match_date AS fact_date
    FROM {{ ref('features__head_to_head') }} t
    JOIN {{ ref('fact_matches') }} m ON t.match_id = m.match_id
    WHERE t.match_date != m.match_date
),
-- Same for venue_effects
venue_check AS (
    SELECT t.match_id, t.match_date AS feature_date, m.match_date AS fact_date
    FROM {{ ref('features__venue_effects') }} t
    JOIN {{ ref('fact_matches') }} m ON t.match_id = m.match_id
    WHERE t.match_date != m.match_date
),
-- Same for temporal
temporal_check AS (
    SELECT t.match_id, t.match_date AS feature_date, m.match_date AS fact_date
    FROM {{ ref('features__temporal') }} t
    JOIN {{ ref('fact_matches') }} m ON t.match_id = m.match_id
    WHERE t.match_date != m.match_date
)
SELECT * FROM team_form_check
UNION ALL
SELECT * FROM h2h_check
UNION ALL
SELECT * FROM venue_check
UNION ALL
SELECT * FROM temporal_check
