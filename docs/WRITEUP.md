# IPL Winner Prediction — Project Writeup

## What this is

An end-to-end data engineering and ML pipeline that predicts IPL match outcomes. Built as a portfolio project with two unusual constraints:

1. **Compliance-first data sourcing.** Every data source has a documented legal basis. No scraping of sites that prohibit it.
2. **Production-grade discipline at every layer**, not just the headline ML model.

Live demo: [ipl-winner-prediction-sample.streamlit.app](https://ipl-winner-prediction-sample.streamlit.app/)
Source code: [github.com/dharmicreddy/ipl-winner-prediction](https://github.com/dharmicreddy/ipl-winner-prediction)

## Why IPL prediction?

Cricket is rich for modeling. Each IPL match is a clean binary outcome (win/loss). Tournament structure rewards probability calibration (a tournament bracket needs accurate probabilities, not just rankings). The data is genuinely abundant (Cricsheet has ball-by-ball detail). And there is real signal — venue effects, team form, head-to-head, toss decisions — without the dataset being so trivial that any approach works.

The choice that distinguishes this project from typical IPL-prediction repos on GitHub is the **data sourcing discipline**. Most public IPL projects scrape ESPNcricinfo or other sites in violation of their terms. This project uses only:

- **Cricsheet** — ball-by-ball data licensed under ODbL (open database license)
- **Wikipedia** — venue metadata under CC BY-SA
- **CricketData.org** — current fixtures via their public API per their terms

Every source has a documented legal basis in `docs/data-sources.md`. This isn't lawyer-speak; it's the difference between a portfolio project that could be reused by a real company and one that couldn't.

## What it does

The full pipeline:

1. **Ingest** — Cricsheet bulk download, Wikipedia API for venues, CricketData API for upcoming fixtures
2. **Warehouse** — Postgres-backed dbt project with bronze (raw), silver (cleaned), and gold (star schema) layers. SCD-2 snapshots track team rebrandings (Royal Challengers Bangalore → Bengaluru). 108 dbt tests guard against regressions.
3. **Features** — five feature models (team form, head-to-head, venue effects, temporal, match set) with an explicit no-leakage policy: every feature computes strictly as-of the match date.
4. **Train** — three classifiers compared: majority-class baseline, calibrated logistic regression, calibrated XGBoost. Walk-forward evaluation: train on 2022, validate on early 2023, test on late 2023 + 2024.
5. **Orchestrate** — local Airflow DAG (LocalExecutor) for development; GitHub Actions weekly cron for production.
6. **Serve** — multipage Streamlit dashboard with prediction, calibration analysis, and data exploration.

## The engineering story

Eight ADRs (`docs/decisions/`) document every architectural choice. Highlights:

- **ADR-001 — Hosting**: hybrid local Airflow + GitHub Actions production. Free tier where possible; paid services only with explicit reason.
- **ADR-004 — Evaluation**: time-based splits with walk-forward training. No random splits — that would leak future information into the past.
- **ADR-005 — Compliance**: every data source must have a legal basis documented before ingestion code is written.
- **ADR-007 — No leakage**: features are computed strictly as-of match date. Enforced by a singular dbt test.
- **ADR-008 — Orchestration choices**: LocalExecutor over Celery, ephemeral CI Postgres over hosted, BashOperator pattern shared between Airflow and GHA.

The orchestration layer especially demonstrates discipline. Both Airflow and GitHub Actions call the same Python entrypoints — there's no duplicate logic between local demo and production schedule. A read-only code mount with writable data overlays prevents Airflow tasks from accidentally modifying source code. CI uses an ephemeral Postgres so each weekly run starts fresh and proves the pipeline still works end-to-end.

## The honest modeling story

Three classifiers on the holdout split (102 matches, late 2023 + 2024):

| Model | Accuracy | Brier | ECE |
|---|---|---|---|
| Majority-class baseline | 0.500 | 0.250 | 0.000 |
| Calibrated logistic regression | 0.529 | 0.250 | 0.063 |
| **Calibrated XGBoost** | **0.598** | 0.252 | 0.091 |

XGBoost beats the baseline by ~10 percentage points on accuracy. That's the headline. The honest version is in the next two columns:

- **Brier score barely moves.** A coin-flip baseline scores 0.250. The XGBoost scores 0.252 — virtually identical. The model picks up enough signal to classify better than chance, but its probability estimates are not meaningfully sharper than uninformed guessing.
- **ECE (calibration error) is 0.091.** Across decile bins, the model's predicted probability differs from actual win rate by ~9 percentage points on average. It tends to be underconfident at the high end (predicting 60-65% when actual is 80%+).

The calibration page in the dashboard surfaces this analysis interactively. The model card (`docs/MODEL_CARD.md`) documents what works, what doesn't, and what would improve it.

This is intentional. A portfolio project that claims 95% accuracy on a small dataset is either suspicious or uninteresting. A portfolio project that beats baseline by ~10pp on a hard problem with rigorous evaluation and honest calibration analysis is doing real engineering.

## What the dashboard does

The deployed Streamlit app has three pages:

**Predict** — Pick two teams, a venue, and a date. The model returns a calibrated win probability with confidence breakdown. All features (team form over last 5, head-to-head, venue stats, days since last match) are computed in Python at request time using the same as-of logic as the dbt feature models. No leakage.

**Calibration** — Interactive reliability diagram (Plotly) showing predicted vs. actual win rates per decile bin. Includes ECE, Brier score, and an honest caveat about the model's limitations. Hover tooltips show bin counts.

**Data** — Match-level explorer with bat-first metrics and seasonal trends across 218 matches.

The deployment uses a SQLite snapshot bundled in the repo (`dashboard/data/ipl.sqlite`) so the cloud-deployed app works without database access. The same dashboard code runs against Postgres locally — see `dashboard/lib/data.py`.

## What I would do differently

The interesting failure modes:

**Cricsheet's 218 IPL matches across 2022-2024 is a small dataset.** Better would be ball-by-ball features (current run rate, wickets in hand, target left) at decision points within a match — not just match-level priors. The current model has no information that distinguishes "high-scoring slugfest" from "low-scoring grind."

**Six venues in the encoder is too narrow.** The model trained only on 2022, where IPL was concentrated in fewer venues due to COVID protocols. A user picking the 17 venues from later seasons gets all-zeros for the categorical component. Better would be retraining on the full 2022-2024 set with venue clustering.

**Calibration analysis only shows holdout — not training behavior.** Training accuracy is much higher than holdout (overfitting). A reliability diagram showing both would tell a fuller story.

**The asset rebuild is manual.** The GitHub Actions weekly cron runs the pipeline but doesn't auto-commit fresh `ipl.sqlite` and `model.pkl` back to the repo. Adding auto-commit (with a deploy key) is straightforward but requires bypassing branch protection — out of scope for this version.

## Lessons internalized

A few things this project taught me that I would carry to the next:

1. **The data layer is more work than the model layer**, and most of it isn't sexy. dbt model tests, SCD snapshots, leakage guards, schema drift handling — all unglamorous, all critical.
2. **Calibration matters more than accuracy** when probabilities will be consumed downstream. A 70% prediction should win 70% of the time, not 50% of the time.
3. **Honest reporting is more compelling than inflated claims**. "Beats baseline by 10pp on accuracy but Brier barely moves and ECE is 0.091" is a stronger signal of engineering maturity than "59.8% accuracy on IPL prediction."
4. **Branch protection plus PR review even for solo work** forces clean commit history. Every change in this repo went through a PR. Reviewers (recruiters, hiring managers) can see the discipline in the commit graph.
5. **Two-track orchestration (local Airflow + production GHA cron) is worth the duplication** because each track tells a different story to a different audience. Reviewers see both.

## Tech stack summary

- **Languages**: Python 3.13, SQL
- **Data**: PostgreSQL 16, SQLite (deployment), dbt 1.11
- **ML**: scikit-learn, XGBoost, MLflow
- **Orchestration**: Apache Airflow (LocalExecutor), GitHub Actions
- **Serving**: Streamlit (Streamlit Community Cloud)
- **Compliance**: All data sources licensed for use; documented in `docs/data-sources.md`

## Closing

The completed project is on GitHub at [github.com/dharmicreddy/ipl-winner-prediction](https://github.com/dharmicreddy/ipl-winner-prediction).

The live demo is at [ipl-winner-prediction-sample.streamlit.app](https://ipl-winner-prediction-sample.streamlit.app/).

— Dharmic Reddy
