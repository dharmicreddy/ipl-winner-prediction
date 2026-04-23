-- Migration 006: gold venue dimension and upcoming matches view
-- Phase 3 / Chunk 3.5
--
-- Joins silver.matches to silver.venues via silver.venue_aliases so that
-- Phase 5 feature engineering can access venue attributes (lat/lng, descriptions)
-- without having to know about the Cricsheet-vs-Wikipedia name mapping.

CREATE OR REPLACE VIEW gold.dim_venues AS
SELECT
    a.venue_alias        AS venue_raw,     -- as it appears in silver.matches.venue
    v.wiki_title,
    v.display_title,
    v.description,
    v.extract,
    v.latitude,
    v.longitude,
    v.wikipedia_url
FROM silver.venue_aliases a
JOIN silver.venues v ON v.wiki_title = a.wiki_title;

-- Dashboard-facing view: upcoming or live IPL matches.
-- Status filtering keeps only matches that haven't ended.
CREATE OR REPLACE VIEW gold.upcoming_ipl_matches AS
SELECT
    fixture_id,
    match_name,
    match_date,
    team_1,
    team_2,
    venue,
    status,
    series_name
FROM silver.fixtures
WHERE is_ipl = true
  AND (status IS NULL OR status NOT ILIKE '%won by%')
ORDER BY match_date;

INSERT INTO public.schema_migrations (version)
VALUES ('006_gold_venues_and_fixtures')
ON CONFLICT (version) DO NOTHING;
