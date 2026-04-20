# ADR-002: Warehouse Engine

**Status:** Accepted
**Date:** Phase 1

## Context

Need a SQL warehouse that supports dbt, runs free, handles our data volume (full IPL ball-by-ball is <1 GB), and is reproducible for reviewers who clone the repo.

Candidates: PostgreSQL, DuckDB, SQLite, BigQuery free tier, Snowflake free trial.

## Decision

**PostgreSQL 16, containerised via Docker locally. Neon free tier as the optional hosted variant for reviewers who want to poke at the dashboard backend.**

## Rationale

- **Dbt maturity.** The Postgres adapter is first-class and well-documented; important given the engineer is new to dbt.
- **Dev-prod parity.** Same engine locally and in any hosted deployment. DuckDB is lovely for analytics but diverges from typical production warehouses — a portfolio project benefits from showing production-shaped choices.
- **Dashboard backend.** Streamlit can query Postgres directly over the network (Neon). DuckDB would require bundling the file or a custom API.
- **Reproducibility.** `docker compose up` gives every reviewer an identical warehouse.

## Alternatives considered

- **DuckDB.** Faster for local analytics and zero setup. Rejected because Streamlit + DuckDB deployment is awkward and reviewers expect a "real" warehouse.
- **SQLite.** Too limited for dbt idioms we want to demonstrate (schemas, window functions in context, concurrency).
- **BigQuery free tier.** Capable but introduces Google Cloud auth complexity and the free quota model is opaque to reviewers.
- **Snowflake trial.** 30-day clock is hostile to a portfolio project with no end date.

## Consequences

- Reviewers cloning the repo need Docker installed. Acceptable — documented in README.
- If data volume ever outgrows Postgres (it will not for this project), we revisit.
