"""Predict match outcome — interactive prediction page.

Lets the user pick teams, venue, and match date, then computes features
as-of that date and shows the calibrated win probability.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from dashboard.lib.data import get_backend_name, query  # noqa: E402
from dashboard.lib.model import load_model  # noqa: E402
from dashboard.lib.predict import predict  # noqa: E402

st.set_page_config(page_title="Predict", page_icon="🎯", layout="wide")


@st.cache_resource
def get_model():
    return load_model()


@st.cache_data(ttl=300)
def get_teams() -> list[str]:
    df = query("SELECT DISTINCT team_canonical FROM gold.dim_teams ORDER BY team_canonical")
    return df["team_canonical"].tolist()


@st.cache_data(ttl=300)
def get_venues() -> list[str]:
    """Pull venues from fact_matches — that's the column the model trained on."""
    df = query(
        "SELECT DISTINCT venue FROM gold.fact_matches WHERE venue IS NOT NULL ORDER BY venue"
    )
    return df["venue"].tolist()


def main():
    st.title("🎯 Predict match outcome")
    st.caption(
        f"Backend: **{get_backend_name()}** • "
        "Calibrated XGBoost classifier (Phase 6). "
        "Features computed strictly as-of the match date — no leakage."
    )

    artifact = get_model()
    teams = get_teams()
    venues = get_venues()

    # Surface model coverage to the user up-front.
    encoder_teams = set(artifact.encoder.categories_[0])
    encoder_venues = set(artifact.encoder.categories_[2])

    with st.expander("Model coverage", expanded=False):
        st.markdown(f"""
        The model was trained on the **2022 season** (74 matches), validated on
        early 2023, and tested on late 2023 + 2024 (102 matches, **59.8% accuracy**).

        - **Teams known to the model**: {len(encoder_teams)} / {len(teams)} in the database
        - **Venues known to the model**: {len(encoder_venues)} / {len(venues)} in the database

        Picks outside those sets still produce predictions, but the model
        treats unknown teams/venues as zero-features for the categorical
        component. Numeric features (form, H2H, venue stats) still apply
        based on whatever historical data exists.
        """)

    # ---- Input form ----
    with st.form("predict_form"):
        col1, col2 = st.columns(2)
        team_home = col1.selectbox(
            "Home team (bats first)",
            options=teams,
            index=teams.index("Chennai Super Kings") if "Chennai Super Kings" in teams else 0,
            help="The team batting first in the match",
        )
        team_away = col2.selectbox(
            "Away team (bats second)",
            options=teams,
            index=teams.index("Mumbai Indians") if "Mumbai Indians" in teams else 1,
            help="The team batting second",
        )

        col3, col4 = st.columns(2)
        venue = col3.selectbox(
            "Venue",
            options=venues,
            index=0,
            help="The stadium hosting the match",
        )

        # Default to a recent date in 2024 — within our data range
        default_date = date(2024, 5, 15)
        target_date = col4.date_input(
            "Match date",
            value=default_date,
            min_value=date(2022, 3, 1),
            max_value=date(2025, 12, 31),
            help="Target match date. Features use only matches strictly before this date.",
        )

        submitted = st.form_submit_button("🎯 Predict", type="primary", use_container_width=True)

    if not submitted:
        st.info(
            "Pick teams, venue, and date, then click Predict to see the calibrated win probability."
        )
        return

    if team_home == team_away:
        st.error("Home and away teams must be different.")
        return

    # ---- Run prediction ----
    with st.spinner("Computing features and running model..."):
        try:
            result = predict(
                target_date=target_date,
                team_home=team_home,
                team_away=team_away,
                venue=venue,
                artifact=artifact,
            )
        except Exception as exc:
            st.error(f"Prediction failed: {exc}")
            return

    # ---- Results panel ----
    st.divider()
    st.subheader("Prediction")

    p_first = result["probability_batting_first_wins"]
    p_second = result["probability_batting_second_wins"]
    confidence = result["confidence"]

    col_a, col_b, col_c = st.columns(3)
    col_a.metric(
        f"{team_home} wins (batting first)",
        f"{p_first:.1%}",
    )
    col_b.metric(
        f"{team_away} wins (batting second)",
        f"{p_second:.1%}",
    )

    confidence_color = {
        "high": "🟢",
        "medium": "🟡",
        "low": "🔴",
    }
    col_c.metric(
        "Confidence",
        f"{confidence_color[confidence]} {confidence}",
        help="Distance from 50/50: high ≥ 20pp, medium ≥ 10pp, low < 10pp",
    )

    # Visual probability bar
    st.progress(p_first, text=f"{team_home} {p_first:.1%}  ⟷  {team_away} {p_second:.1%}")

    # ---- Calibration caveat ----
    st.warning(
        "⚠️ **Calibration caveat**: this model has a holdout Brier score of 0.252 "
        "(barely better than the 0.250 baseline) and ECE of 0.091. Treat probabilities "
        "as directional, not as exact betting odds. See the Calibration page for details."
    )

    # ---- Feature breakdown ----
    st.divider()
    st.subheader("Features used by the model")
    st.caption(
        "All features computed using only matches strictly before the target date (no leakage)."
    )

    features = result["features"].to_dict()

    feat_col1, feat_col2 = st.columns(2)

    with feat_col1:
        st.markdown(f"**{team_home} (home, bats first)**")
        st.write(f"- Last-5 form: **{_fmt_pct(features['team_home_form_5'])}**")
        st.write(f"- Days rest: **{_fmt_int(features['days_since_team_home_last_match'])}**")
        h2h_wins = features["team_home_h2h_wins"]
        h2h_played = features["h2h_matches_played"]
        h2h_pct = _fmt_pct(features["team_home_h2h_win_rate"])
        st.write(f"- H2H wins vs opponent: **{h2h_wins} / {h2h_played} ({h2h_pct})**")

    with feat_col2:
        st.markdown(f"**{team_away} (away, bats second)**")
        st.write(f"- Last-5 form: **{_fmt_pct(features['team_away_form_5'])}**")
        st.write(f"- Days rest: **{_fmt_int(features['days_since_team_away_last_match'])}**")
        st.write(f"- Match number in season: **{features['match_number_in_season']}**")

    st.markdown(f"**Venue: {venue}**")
    st.write(f"- Prior matches at venue: **{features['venue_matches_played']}**")
    st.write(f"- Bat-first win rate at venue: **{_fmt_pct(features['venue_bat_first_win_rate'])}**")


def _fmt_pct(v):
    if v is None:
        return "n/a"
    return f"{v * 100:.1f}%"


def _fmt_int(v):
    if v is None:
        return "n/a"
    return str(v)


main()
