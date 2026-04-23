-- Migration 004: silver.venues
-- Phase 3 / Chunk 3.3
--
-- One row per canonical Wikipedia title. Populated from bronze.http_responses
-- rows where source = 'wikipedia'.

CREATE TABLE IF NOT EXISTS silver.venues (
    wiki_title       text PRIMARY KEY,
    display_title    text NOT NULL,
    description      text,
    extract          text,
    latitude         double precision,
    longitude        double precision,
    wikipedia_url    text,
    content_sha256   text NOT NULL,
    raw_response_id  bigint NOT NULL REFERENCES bronze.http_responses(response_id),
    parsed_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_silver_venues_display_title
    ON silver.venues (display_title);

-- Optional: a mapping view that joins Cricsheet venue spellings to
-- silver.venues via the YAML-derived table. For now, we'll load that
-- mapping as a seed table in the parser.

CREATE TABLE IF NOT EXISTS silver.venue_aliases (
    venue_alias  text PRIMARY KEY,           -- Cricsheet spelling
    wiki_title   text NOT NULL REFERENCES silver.venues(wiki_title)
);

INSERT INTO public.schema_migrations (version)
VALUES ('004_silver_venues')
ON CONFLICT (version) DO NOTHING;
