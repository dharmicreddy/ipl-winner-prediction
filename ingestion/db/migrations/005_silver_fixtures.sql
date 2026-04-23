-- Migration 005: silver.fixtures from CricketData.org
-- Phase 3 / Chunk 3.4

CREATE TABLE IF NOT EXISTS silver.fixtures (
    fixture_id       text PRIMARY KEY,
    match_name       text,
    match_type       text,
    status           text,
    venue            text,
    match_date       timestamptz,
    series_name      text,
    team_1           text,
    team_2           text,
    is_ipl           boolean NOT NULL DEFAULT false,
    raw_response_id  bigint NOT NULL REFERENCES bronze.http_responses(response_id),
    parsed_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_silver_fixtures_is_ipl_date
    ON silver.fixtures (is_ipl, match_date);

CREATE INDEX IF NOT EXISTS ix_silver_fixtures_status
    ON silver.fixtures (status);

INSERT INTO public.schema_migrations (version)
VALUES ('005_silver_fixtures')
ON CONFLICT (version) DO NOTHING;
