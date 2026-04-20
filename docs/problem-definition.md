# Problem Definition

## What we are predicting

**Match-level winner of an IPL match, pre-match.** Given two teams, venue, toss outcome, and pre-match context (recent form, head-to-head, squad availability), output a calibrated probability that Team A wins.

Tournament-level winner (who lifts the trophy) is derived by Monte Carlo simulating remaining fixtures using the match-level probabilities. It is *not* trained directly — only one label per season exists.

## Target formulation

- Binary classification: `P(team_a_wins)`
- IPL has a super-over for ties, so no draw class is needed
- Rain-affected no-results are excluded from the training set

## Success metrics

| Metric | Purpose | Target |
|---|---|---|
| Accuracy (holdout season) | Headline number for the dashboard | Beat baseline |
| Log-loss | Proper scoring rule — penalises overconfidence | Lower than baseline |
| Brier score | Calibration quality | Key for tournament simulator |
| Reliability diagram | Visual calibration check | Near diagonal |

**Baselines to beat:**
1. Always pick the team batting second (~55% historical win rate in IPL)
2. Always pick the team with the better win rate over the previous season
3. Logistic regression on toss + venue only

If the model does not clearly exceed all three, it is not shipping. A calibrated baseline is also interesting content for the write-up.

## Evaluation discipline

- **Time-based split only.** Train on seasons through N-1, validate on season N, test on season N+1. No random splits at any point.
- **No leakage.** Features computed as of match start; post-match stats never leak into pre-match features. Enforced by explicit `as_of` timestamps in feature SQL.
- **Walk-forward evaluation** for the final report: retrain at each season boundary and evaluate on the next, producing a realistic accuracy curve over time.

## Scope — in

- Pre-match prediction
- IPL only
- Men's tournament
- From 2008 season onward (full T20 IPL history)

## Scope — out (v1)

- In-play / live ball-by-ball prediction (requires streaming, huge scope bump)
- Player-level fantasy predictions
- Betting-odds integration
- WPL, other T20 leagues
- Mobile app, user accounts, auth

## Non-goals

- Beating Vegas. We are a portfolio project, not a sportsbook.
- Explaining the *causal* drivers of wins. We model correlational predictors.
- Real-time inference latency. Weekly refresh is enough.
