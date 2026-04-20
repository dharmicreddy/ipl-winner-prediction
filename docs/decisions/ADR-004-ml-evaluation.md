# ADR-004: ML Evaluation Protocol

**Status:** Accepted
**Date:** Phase 1

## Context

Match-winner prediction is a time-series problem dressed up as classification. Naive random train/test splits cause catastrophic leakage — a match in 2019 informs predictions for 2018. Most IPL-prediction projects online make exactly this mistake; not making it is a differentiator.

## Decision

1. **Splits are strictly time-based.** Train on seasons through N-1, validate on season N, test on season N+1. Never shuffle.
2. **Features are computed as-of match start.** Every feature SQL includes an `as_of_timestamp` bound; post-match stats cannot leak in.
3. **Walk-forward evaluation for the headline number.** For each season from ~2015 onward, retrain using only data prior to that season and predict it. The resulting accuracy-over-time chart goes on the dashboard.
4. **Probability calibration is mandatory, not optional.** Raw classifier scores go through isotonic or Platt calibration, evaluated on held-out data, before feeding the tournament simulator.
5. **Baselines are reported alongside every model.** If a new feature does not move the needle over baseline, it gets cut.

## Rationale

- Temporal leakage is the single most common flaw in cricket-prediction portfolios. Being explicit about this in both docs and code is a strong quality signal.
- Calibration matters because the tournament simulator multiplies probabilities across a bracket; overconfident probabilities compound into nonsense.
- Walk-forward is more honest than a single holdout — shows how the model would actually have performed season by season.

## Consequences

- Lower reported accuracy than a leaky random-split model would show. This is correct and will be explained in the write-up.
- More compute: walk-forward retrains ~10 models instead of one. Still cheap at our scale.
- Feature engineering code must handle the `as_of` constraint cleanly — this shapes the feature-store design in Phase 5.
