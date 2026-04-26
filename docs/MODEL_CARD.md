# Model Card: IPL Match Predictor

## Overview

A binary classifier predicting whether the team batting first wins an IPL match. Trained on 2022 IPL season data, evaluated on 2023-2024 with strict walk-forward methodology.

This model card follows a simplified version of the [Google Model Card template](https://modelcards.withgoogle.com/about), adapted for a personal portfolio project.

## Intended use

**Primary use:** demonstrating end-to-end MLOps practice for a tabular binary classification problem in a sports prediction context. Suitable for portfolio review, not real-money betting.

**Out-of-scope uses:**
- Wagering or financial decisions
- Predicting individual player performance
- Real-time predictions during matches (the model uses only pre-match features)
- Other cricket leagues (different rules, different distributions)

## Training data

**Source:** [Cricsheet](https://cricsheet.org) — historical match data licensed under [ODbL](https://opendatacommons.org/licenses/odbl/1-0/).

**Coverage:** 218 IPL matches from the 2022, 2023, and 2024 seasons. After filtering one no-result match, 218 matches with valid winners.

**Splits (per ADR-004 walk-forward methodology):**
- **train**: 2022 season, 74 matches
- **val**: 2023 before May 1, 42 matches
- **holdout**: 2023 from May 1 + all 2024, 102 matches

Splits are strictly chronological. No data from after a match's date influences its features (per ADR-007).

## Features

Engineered in dbt's `features` schema. All features computed as-of match date (`match_date < target_match_date`):

| Feature | Source model | Description |
|---|---|---|
| team_home_form_5 | features__team_form | Win rate over last 5 matches |
| team_away_form_5 | features__team_form | Win rate over last 5 matches |
| h2h_matches_played | features__head_to_head | Count of prior head-to-head meetings |
| team_home_h2h_wins | features__head_to_head | Home team's historical wins vs this opponent |
| team_home_h2h_win_rate | features__head_to_head | Win rate as a fraction |
| venue_matches_played | features__venue_effects | Sample size for the venue |
| venue_bat_first_win_rate | features__venue_effects | Bat-first win rate at this venue |
| days_since_team_home_last_match | features__temporal | Rest days for home team |
| days_since_team_away_last_match | features__temporal | Rest days for away team |
| match_number_in_season | features__temporal | 1-indexed within current season |

Plus one-hot encodings of `team_home`, `team_away`, and `venue` (~27 columns).

## Models compared

Three models trained on the same train split, evaluated identically:

| Model | Approach | Notes |
|---|---|---|
| Majority-class baseline | Predicts training-set positive rate (0.50) | Floor that real models must beat |
| Logistic regression | Mean imputation + StandardScaler + LogisticRegression + Platt calibration | Linear baseline, calibrated |
| XGBoost | Native NaN handling + grid search across 24 hyperparameter combos + Platt calibration | Best discriminator |

XGBoost's hyperparameter grid was tuned by **val brier_score** (lower = better calibrated). Holdout was never seen during tuning.

## Holdout evaluation

| Model | Accuracy | ROC-AUC | Brier Score | Log Loss | ECE |
|---|---|---|---|---|---|
| Baseline | 0.500 | 0.500 | 0.250 | 0.693 | 0.000 |
| Logistic regression | 0.529 | 0.556 | 0.250 | 0.694 | 0.063 |
| **XGBoost** | **0.598** | 0.548 | 0.252 | 0.698 | 0.091 |

XGBoost beats baseline by **9.8 percentage points** on accuracy. It is meaningfully better at *picking winners* than predicting majority class.

However: **calibration remains poor**. Brier score barely moves from baseline; ECE is highest for XGBoost (0.091, vs LR 0.063). Probabilistic confidence values are not trustworthy as decision-input.

See `docs/img/calibration_holdout.png` for the reliability diagram.

## Calibration analysis

The reliability diagram (predicted probability vs. observed frequency) shows:

- **Baseline** sits at the y=0.5 horizontal line — it always predicts 0.5 and matches reality only because the prior is also 0.5.
- **Logistic regression** deviates from the diagonal moderately. Its predictions in the 0.4–0.7 range are reasonably calibrated; predictions outside that range are less so.
- **XGBoost** deviates more significantly. It is overconfident in its high-probability predictions: when it says 80%, reality is closer to 60-65%.

This is a known XGBoost behavior. Tree ensembles produce peaked probability outputs; on a small dataset (74 training rows), Platt calibration via 3-fold CV cannot fully correct the gap.

## Why calibration matters here

Per ADR-004, this project values calibration over raw accuracy. A 60% calibrated probability is more useful than a 60% uncalibrated probability for any downstream decision. For real-world betting use (out of scope here), accuracy without calibration is dangerous: the model would systematically overstate its confidence, leading to overaggressive wagers.

## Limitations

1. **Small training set (74 matches).** Three IPL seasons isn't enough to learn stable team-by-team patterns. The 0.94 train roc_auc vs 0.55 holdout roc_auc gap is severe overfitting.

2. **Distribution shift across seasons.** Player rosters change. Coaching changes. The 2024 IPL had different overall scoring patterns than 2022. The model has no mechanism to adapt.

3. **Team rebrandings.** "Royal Challengers Bangalore" → "Bengaluru" in 2024 is handled by the seed canonical mapping. But future rebrandings would require seed updates before re-training. The team identity feature is fragile.

4. **No bowling/batting depth features.** A team's actual lineup quality matters more than its pre-match form. Phase 5 didn't engineer player-aggregate features — that's a known gap.

5. **One-hot team and venue features have very little training data per column.** With ~10 teams and ~17 venues, each one-hot column has only 7-15 training matches. Coefficients are noisy.

## Recommendations for improving the model

- **More data.** 5+ IPL seasons would meaningfully reduce variance. Currently the project only goes 2022-2024 due to scope.
- **Player-aggregate features.** Compute team-strength estimates from individual player win/loss rates and rest days.
- **Drop one-hot encodings.** Test XGBoost with numeric-only features. The team/venue one-hots may be hurting more than helping.
- **Isotonic calibration on a separate calibration set.** Replace 3-fold Platt scaling with a held-out calibration set + isotonic regression. Better for tree models with peaked outputs.

## Conclusion

XGBoost achieves 60% accuracy on holdout (vs. 50% baseline) — meaningfully better than chance. But probabilistic confidence is not trustworthy: ECE 0.091 indicates ~9% systematic overconfidence on high-probability predictions.

For deployment: use XGBoost's class predictions ("which team wins") with caution; do not use its probability outputs as input to financial decisions. With the current dataset size and feature set, this is honestly the limit of what the model can achieve.

The portfolio value is in the rigor: walk-forward eval, calibration analysis, honest reporting of limitations.
