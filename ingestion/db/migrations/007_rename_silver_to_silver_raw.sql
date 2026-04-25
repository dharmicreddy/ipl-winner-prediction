-- Migration 007: rename silver.* to silver_raw.*
-- Phase 4 / Chunk 4.2
--
-- dbt will take over the `silver` schema in Chunk 4.2 Part B. Existing
-- Python-populated tables move to `silver_raw` so dbt can build a clean
-- `silver` namespace of its own.
--
-- Also drops the gold views that Python/raw SQL currently owns. dbt will
-- rebuild them in Chunk 4.3.

CREATE SCHEMA IF NOT EXISTS silver_raw;

-- Move existing silver tables into silver_raw.
-- Idempotent via IF EXISTS checks in pg_tables.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'silver' AND tablename = 'matches') THEN
        ALTER TABLE silver.matches SET SCHEMA silver_raw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'silver' AND tablename = 'deliveries') THEN
        ALTER TABLE silver.deliveries SET SCHEMA silver_raw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'silver' AND tablename = 'venues') THEN
        ALTER TABLE silver.venues SET SCHEMA silver_raw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'silver' AND tablename = 'venue_aliases') THEN
        ALTER TABLE silver.venue_aliases SET SCHEMA silver_raw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'silver' AND tablename = 'fixtures') THEN
        ALTER TABLE silver.fixtures SET SCHEMA silver_raw;
    END IF;
END $$;

-- Drop the gold views that were built on the old silver.* names.
-- dbt will rebuild them in Chunk 4.3.
DROP VIEW IF EXISTS gold.fact_matches CASCADE;
DROP VIEW IF EXISTS gold.dim_venues CASCADE;
DROP VIEW IF EXISTS gold.upcoming_ipl_matches CASCADE;

INSERT INTO public.schema_migrations (version)
VALUES ('007_rename_silver_to_silver_raw')
ON CONFLICT (version) DO NOTHING;
