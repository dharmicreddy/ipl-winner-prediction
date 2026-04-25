-- Migration 002: gold.fact_matches (RETIRED)
--
-- This migration originally created the gold.fact_matches view via raw SQL.
-- As of Phase 4 / Chunk 4.3, gold.fact_matches is built and owned by dbt.
-- See `warehouse/models/gold/fact_matches.sql`.
--
-- Migration 007 drops the gold view this used to create, and dbt rebuilds it
-- via `dbt build --project-dir warehouse`.
--
-- This file is preserved as a no-op so existing migration sequences stay
-- intact. Do NOT delete or renumber.

INSERT INTO public.schema_migrations (version)
VALUES ('002_gold_fact_matches')
ON CONFLICT (version) DO NOTHING;
