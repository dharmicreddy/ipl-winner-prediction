# ADR-006: API Ingestion Patterns

**Status:** Accepted
**Date:** Phase 1 (revised)

## Context

With scraping removed from the project (ADR-005), all ingestion happens via HTTPS GETs against bulk downloads (Cricsheet) or JSON APIs (Wikipedia, optionally CricketData.org). We need consistent patterns for how these calls are structured, to ensure both compliance and engineering quality.

## Decision

All ingestion code follows these rules:

1. **Identifiable User-Agent** on every request: `ipl-prediction/<version> (+https://github.com/<user>/<repo>)`
2. **Exponential backoff with jitter** on HTTP 429 and 5xx, capped at 5 retries
3. **Respect `Retry-After`** response headers absolutely
4. **Raw response lands in bronze before parsing.** Bronze row has: source URL, timestamp, response bytes, status code, response headers (JSON-serialized). Parsing is a separate step operating on bronze.
5. **One network call per logical entity per run.** Deduplicate before fetching — never re-hit a source to re-parse.
6. **Rate limit budget** is documented per source in `ingestion/rate_limits.yaml` and enforced with a token bucket.
7. **API keys** loaded from environment variables; never committed. `.env.example` lists the required variables.

## Rationale

These are the patterns a senior engineer expects to see reviewing the repo. They also protect against accidental ToS breach from bugs (e.g. an infinite retry loop).

## Consequences

- Every ingestion module has a common shape: `fetch -> land_bronze -> parse_to_silver`.
- Integration tests can operate against bronze fixtures without hitting the network.
- Adding a new source is a well-defined template.
