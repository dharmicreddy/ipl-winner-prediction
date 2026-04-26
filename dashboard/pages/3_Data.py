"""Data exploration page — bat-first metrics and recent matches.

This is the original Phase 2 vertical-slice dashboard, refactored to use
the new data abstraction layer (Postgres locally, SQLite in deployment).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import streamlit as st  # noqa: E402

from dashboard.lib.data import get_backend_name, query  # noqa: E402

st.set_page_config(
    page_title="IPL Prediction — Data",
    page_icon="🏏",
    layout="wide",
)

st.title("📊 Match data explorer")
st.caption(
    f"Backend: **{get_backend_name()}** • "
    "Data: Cricsheet (ODbL), Wikipedia (CC BY-SA), CricketData.org. "
    "Warehouse built via dbt."
)


@st.cache_data(ttl=300)
def load_matches():
    return query("""
        SELECT season, match_date, venue, city,
               team_home, team_away, toss_winner, toss_decision,
               batting_first, winner, batting_first_won,
               win_margin_type, win_margin
        FROM gold.fact_matches
        ORDER BY match_date
    """)


@st.cache_data(ttl=300)
def load_upcoming():
    return query("""
        SELECT match_date, team_1, team_2, venue, status, series_name
        FROM gold.upcoming_ipl_matches
        ORDER BY match_date
    """)


df = load_matches()
if df.empty:
    st.warning("No matches in fact_matches. Run the pipeline first.")
    st.stop()

# Top-level metrics
col1, col2, col3 = st.columns(3)
col1.metric("Matches loaded", f"{len(df):,}")
col2.metric("Seasons", df["season"].nunique())
col3.metric("Bat-first win %", f"{100.0 * df['batting_first_won'].mean():.1f}%")

st.divider()

# Matches by season
st.subheader("Matches by season")
by_season = df.groupby("season").size().reset_index(name="matches")
st.bar_chart(by_season, x="season", y="matches")

# Bat-first by season
st.subheader("Batting first: win rate by season")
bf_by_season = (
    df.groupby("season")["batting_first_won"]
    .agg(["mean", "count"])
    .reset_index()
    .rename(columns={"mean": "bat_first_win_rate", "count": "matches"})
)
bf_by_season["bat_first_win_rate"] = (bf_by_season["bat_first_win_rate"] * 100).round(1)
st.bar_chart(bf_by_season, x="season", y="bat_first_win_rate")

# Upcoming
st.divider()
st.subheader("Upcoming IPL matches")
try:
    upcoming = load_upcoming()
    if upcoming.empty:
        st.info("No upcoming IPL matches in the current fixtures data.")
    else:
        st.dataframe(upcoming, width="stretch")
except Exception as exc:
    st.warning(f"Upcoming matches unavailable: {exc}")

# Recent matches
st.subheader("Recent matches (latest 20)")
st.dataframe(df.tail(20), width="stretch")

st.divider()
st.caption(
    "Data: [Cricsheet](https://cricsheet.org) (ODbL). "
    "This project uses data from Cricsheet, made available under the ODbL."
)
