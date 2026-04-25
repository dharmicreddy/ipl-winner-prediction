# ADR-007: Feature engineering policy — no leakage

## Status

Accepted — Phase 5

## Context

The IPL match prediction model needs input features (team form, head-to-head record, venue effects, etc.) computed for every match in `gold.fact_matches`. The hardest correctness constraint in feature engineering for predictive ML is **temporal leakage**: a feature that uses information from the future, including from the match it's labeling.

Without strict policy, leakage creeps in via three patterns:

1. **Aggregating across all matches** — `AVG(...) OVER (PARTITION BY team)` includes the current match's outcome in its own feature.
2. **Closed-interval predicates** — `WHERE other.match_date <= current.match_date` accidentally includes same-day matches, which in a tournament setting can mean the model sees today's results.
3. **Joining to gold tables that don't carry temporal context** — e.g. computing player career stats from `dim_players` then joining as a feature, where `dim_players` aggregates over all time including post-match.

A model trained on leaked features achieves unrealistic test accuracy, then collapses in production. This is the most common failure mode in ML portfolios.

## Decision

All features for match M (with `match_date = D`) are computed using only rows from `gold.fact_matches` where `match_date < D` — strictly before, never on or after.

We enforce this at three levels:

**1. Convention in SQL.** Every feature model uses an as-of correlated subquery or LATERAL join with the predicate `h.match_date < m.match_date`. The strictly-less-than is mandatory.

**2. dbt tests.** A custom dbt test in `warehouse/tests/` verifies that for any row in `feature_set`, no source row contributing to its features has `match_date >= match_date_of_target`.

**3. Walk-forward splits.** Train, validation, and holdout sets are split chronologically:
- Train: 2022 season
- Validation: first half of 2023
- Holdout: second half of 2023 + all of 2024

This ensures the model is evaluated on data strictly after its training data, mimicking production use.

## Consequences

**Positive:**
- Test-set metrics in Phase 6 reflect realistic predictive accuracy
- The pipeline can be deployed to production without subtle bugs
- Reviewers reading the codebase see explicit leakage guards

**Negative:**
- Feature SQL is more verbose (correlated subqueries instead of window functions)
- Earliest matches in the dataset have NaN features (no prior matches to aggregate)
- Some intuitively-useful features become hard to compute correctly (e.g. "this player's form" requires per-player as-of joins, which we defer to a later iteration)

## Alternatives considered

**Alt 1: Compute features once at predict time.** Rejected — defeats the purpose of having a feature store, and recreates the same leakage risk.

**Alt 2: Use window functions with `RANGE BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING`.** Rejected — works in some dialects but Postgres's `RANGE` semantics on dates can include same-day rows, creating subtle leakage.

**Alt 3: Compute features in Python at training time.** Rejected — moves the discipline out of the warehouse and makes it harder to test, harder to inspect, and harder to reuse.

## References

- [Andrej Karpathy on training-test leakage](https://karpathy.github.io/2019/04/25/recipe/)
- [dbt docs: Tests](https://docs.getdbt.com/docs/build/tests)
- ADR-004: time-based splits, walk-forward eval, calibration mandatory
