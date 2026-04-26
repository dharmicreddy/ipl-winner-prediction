"""IPL Match Predictor — Streamlit dashboard entry point.

Streamlit auto-discovers files in `pages/` and creates sidebar navigation.
This file is the landing page (Home).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit launches this file directly without installing the project as a
# package. Add the repo root to sys.path so `from dashboard.lib import ...`
# works.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from dashboard.lib.data import get_backend_name  # noqa: E402

st.set_page_config(
    page_title="IPL Match Predictor",
    page_icon="🏏",
    layout="wide",
)

st.title("🏏 IPL Match Predictor")
st.caption(f"Backend: **{get_backend_name()}**")

st.markdown("""
End-to-end data engineering pipeline predicting IPL match winners. Built on
**licensed open data only** — Cricsheet (ODbL), Wikipedia (CC BY-SA), and
CricketData.org. Demonstrates ingestion, warehousing, transformation, ML,
and serving on free-tier tooling.

Use the sidebar to navigate:

- **Predict** — pick two teams and a venue, see calibrated XGBoost win probabilities
- **Calibration** — reliability diagrams + ECE for honest probability assessment
- **Data** — explore the underlying match-level data and bat-first metrics
""")

st.subheader("Project highlights")

col1, col2, col3 = st.columns(3)
col1.metric("IPL seasons covered", "2022–2024")
col2.metric("Matches in dataset", "218")
col3.metric("Best holdout accuracy", "59.8%")

st.markdown("""
### What this project demonstrates

- **Compliance-first sources**: every source has a documented legal basis (`docs/data-sources.md`)
- **Strict walk-forward evaluation**: train on 2022, val on early 2023, holdout on late 2023 + 2024
- **No data leakage**: features computed strictly as-of match date (ADR-007)
- **Probability calibration**: not just accuracy — Brier score + ECE on reliability diagrams
- **Honest reporting**: the model card documents what works and what doesn't (`docs/MODEL_CARD.md`)
- **Production orchestration**: GitHub Actions weekly cron + local Airflow demo (Phase 7)

### Source code

[github.com/dharmicreddy/ipl-winner-prediction](https://github.com/dharmicreddy/ipl-winner-prediction)

### Tech stack

Python • PostgreSQL • dbt • XGBoost • scikit-learn • MLflow • Airflow • GitHub Actions • Streamlit
""")

st.divider()
st.caption("Data: Cricsheet (ODbL), Wikipedia (CC BY-SA), CricketData.org. Code: MIT licensed.")
