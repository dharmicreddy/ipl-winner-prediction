-- Migration 003: generic bronze.http_responses table
-- Phase 3 / Chunk 3.1
--
-- One bronze table for all HTTP-based ingestion. Source-specific silver
-- parsers know which rows belong to them (filtered by source name and/or URL).

CREATE TABLE IF NOT EXISTS bronze.http_responses (
    response_id    bigserial PRIMARY KEY,
    source         text NOT NULL,             -- 'wikipedia' | 'cricketdata' | ...
    url            text NOT NULL,             -- the exact URL fetched
    status_code    integer NOT NULL,
    response_body  jsonb,                     -- parsed JSON; NULL if non-JSON
    response_text  text,                      -- raw text for non-JSON responses
    content_sha256 text NOT NULL,             -- SHA-256 of raw response bytes
    headers        jsonb NOT NULL,            -- response headers as a JSON object
    fetched_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_bronze_http_source_url_fetched
    ON bronze.http_responses (source, url, fetched_at DESC);

CREATE INDEX IF NOT EXISTS ix_bronze_http_source_sha
    ON bronze.http_responses (source, content_sha256);

INSERT INTO public.schema_migrations (version)
VALUES ('003_http_responses')
ON CONFLICT (version) DO NOTHING;
