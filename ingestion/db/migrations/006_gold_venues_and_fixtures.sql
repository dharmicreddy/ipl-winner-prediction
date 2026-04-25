-- Migration 006: gold.dim_venues + gold.upcoming_ipl_matches (RETIRED)
--
-- This migration originally created two gold views via raw SQL.
-- As of Phase 4 / Chunk 4.3, those views are built and owned by dbt:
--   - gold.dim_venues          → warehouse/models/gold/dim_venues.sql
--   - gold.upcoming_ipl_matches → warehouse/models/gold/upcoming_ipl_matches.sql
--
-- Migration 007 drops the old gold views, and dbt rebuilds them via
-- `dbt build --project-dir warehouse`.
--
-- This file is preserved as a no-op so existing migration sequences stay
-- intact. Do NOT delete or renumber.

INSERT INTO public.schema_migrations (version)
VALUES ('006_gold_venues_and_fixtures')
ON CONFLICT (version) DO NOTHING;
