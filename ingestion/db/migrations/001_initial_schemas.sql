-- Migration 001: Initial schemas and Cricsheet tables
-- Phase 2 / Chunk 2.3

-- Schemas
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Migration tracking — remember which migrations have been applied
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version     text PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now()
);

-- ============================================================================
-- BRONZE — raw, verbatim responses from sources
-- ============================================================================

CREATE TABLE IF NOT EXISTS bronze.cricsheet_matches (
    match_id     text PRIMARY KEY,          -- Cricsheet's filename stem, e.g. "1359475"
    source_url   text NOT NULL,             -- where this came from
    raw_content  jsonb NOT NULL,            -- the full match JSON, verbatim
    ingested_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bronze_cricsheet_ingested_at
    ON bronze.cricsheet_matches (ingested_at DESC);

-- ============================================================================
-- SILVER — parsed, typed, conformed
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.matches (
    match_id         text PRIMARY KEY,
    season           text NOT NULL,                 -- e.g. "2024" — Cricsheet uses string seasons
    match_date       date NOT NULL,
    venue            text,
    city             text,
    team_home        text NOT NULL,                 -- team listed first in Cricsheet
    team_away        text NOT NULL,
    toss_winner      text,
    toss_decision    text,                          -- 'bat' or 'field'
    winner           text,                          -- NULL if no result (rain, tie without super over, etc.)
    win_margin_type  text,                          -- 'runs' | 'wickets' | NULL
    win_margin       integer,                       -- numeric margin, NULL if tie/no-result
    method           text,                          -- 'D/L' if rain-affected, else NULL
    player_of_match  text,                          -- NULL for no-results
    officials        jsonb,                         -- list of umpires/tv umpires
    raw_ingested_at  timestamptz NOT NULL,          -- copied from bronze for lineage
    parsed_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_silver_matches_season
    ON silver.matches (season);
CREATE INDEX IF NOT EXISTS ix_silver_matches_date
    ON silver.matches (match_date);

CREATE TABLE IF NOT EXISTS silver.deliveries (
    match_id         text NOT NULL REFERENCES silver.matches(match_id) ON DELETE CASCADE,
    innings          smallint NOT NULL,             -- 1 or 2 (or 3/4 for super-overs)
    over_number      smallint NOT NULL,             -- 0-indexed, as Cricsheet provides
    ball_in_over     smallint NOT NULL,             -- 1-indexed
    batting_team     text NOT NULL,
    bowling_team     text NOT NULL,
    batter           text NOT NULL,
    non_striker      text NOT NULL,
    bowler           text NOT NULL,
    runs_batter      smallint NOT NULL,
    runs_extras      smallint NOT NULL,
    runs_total       smallint NOT NULL,
    extras_type      text,                          -- 'wides' | 'noballs' | 'byes' | 'legbyes' | 'penalty' | NULL
    wicket_kind      text,                          -- 'bowled' | 'caught' | ... | NULL
    player_out       text,                          -- dismissed batter, NULL if no wicket
    PRIMARY KEY (match_id, innings, over_number, ball_in_over)
);

CREATE INDEX IF NOT EXISTS ix_silver_deliveries_match
    ON silver.deliveries (match_id);

-- Record the migration
INSERT INTO public.schema_migrations (version)
VALUES ('001_initial_schemas')
ON CONFLICT (version) DO NOTHING;
