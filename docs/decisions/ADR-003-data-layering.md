# ADR-003: Bronze / Silver / Gold Data Layering

**Status:** Accepted
**Date:** Phase 1

## Context

We pull from multiple sources (Cricsheet, Wikipedia, optionally CricketData.org) with different schemas and cadences. We need a discipline for organising that data so we can reprocess without re-hitting sources, recover from parsing bugs, and demonstrate mature data engineering practice.

## Decision

Three explicit layers, each in its own Postgres schema:

| Layer | Schema | Contents | Ownership |
|---|---|---|---|
| Bronze | `bronze` | Raw API/download responses, stored verbatim with `ingested_at` timestamps. JSON blobs or bytes as TEXT. | Ingestion scripts |
| Silver | `silver` | Parsed, typed, cleaned. One row per logical event. Conformed naming across sources. | dbt |
| Gold | `gold` | Star schema: `fact_matches`, `fact_ball_by_ball`, `dim_teams`, `dim_players`, `dim_venues`. Query-optimised. | dbt |

Features live in `features` schema, downstream of gold.

## Rationale

- **Idempotent re-processing.** A parser bug found in week 7 does not require re-downloading anything — bronze is the source of truth for "what the source told us". Re-run silver + gold and you are fixed.
- **Debuggability.** When a silver row looks wrong, there is a raw bronze row we can diff against.
- **Audit trail.** `ingested_at` on every bronze row lets us reconstruct pipeline state at any point.
- **Review signal.** The pattern is standard at modern data shops; reviewers will immediately recognise it.

## Retention

- Bronze: retained indefinitely. Small data volume makes this trivial. Compressed via native Postgres TOAST.
- Silver/gold: rebuilt deterministically from bronze. Not backed up separately.
- Snapshots: dbt snapshots for slowly-changing dimensions (squad rosters, player names).

## Consequences

- Three-times storage overhead vs a single-layer design. Trivial at our scale.
- One more mental model to hold. Documented in README and this ADR.
- dbt project is organised with subfolders mirroring the layers (`models/silver/`, `models/gold/`).
