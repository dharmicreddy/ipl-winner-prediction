"""Phase 2 Streamlit vertical slice.

Minimal dashboard that confirms the whole pipeline works:
bronze -> silver -> gold -> Streamlit.

Phase 8 will replace this with the real multi-page dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so `from ingestion...` works when
# Streamlit launches this file directly (no implicit package install).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from ingestion.db.connection import get_connection  # noqa: E402

st.set_page_config(
    page_title="IPL Prediction — Phase 2 Slice",
    page_icon="🏏",
    layout="wide",
)


@st.cache_data(ttl=300)
def load_upcoming_matches() -> pd.DataFrame:
    """Pull upcoming IPL fixtures from gold.upcoming_ipl_matches."""
    query = """
        SELECT match_date, team_1, team_2, venue, status, series_name
        FROM gold.upcoming_ipl_matches
        ORDER BY match_date
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def load_matches() -> pd.DataFrame:
    """Pull completed matches from gold.fact_matches.

    Returns one row per match with derived bat-first columns.
    Cached for 5 minutes.
    """
    query = """
        SELECT season, match_date, venue, city,
               team_home, team_away, toss_winner, toss_decision,
               batting_first, winner, batting_first_won,
               win_margin_type, win_margin
        FROM gold.fact_matches
        ORDER BY match_date
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn)


def main() -> None:
    st.title("🏏 IPL Match Predictor")
    st.caption(
        "Data: Cricsheet (ODbL), Wikipedia (CC BY-SA), CricketData.org. Warehouse built via dbt."
    )

    df = load_matches()
    if df.empty:
        st.warning("No matches in gold.fact_matches. Run the pipeline first.")
        return

    # Top-level stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Matches loaded", f"{len(df):,}")
    col2.metric("Seasons", df["season"].nunique())
    bat_first_win_pct = 100.0 * df["batting_first_won"].mean()
    col3.metric("Bat-first win %", f"{bat_first_win_pct:.1f}%")

    st.divider()

    # Matches by season — the "thin slice" chart
    st.subheader("Matches by season")
    by_season = df.groupby("season").size().reset_index(name="matches")
    st.bar_chart(by_season, x="season", y="matches")

    st.subheader("Batting first: win rate by season")
    bf_by_season = (
        df.groupby("season")["batting_first_won"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "bat_first_win_rate", "count": "matches"})
    )
    bf_by_season["bat_first_win_rate"] = (bf_by_season["bat_first_win_rate"] * 100).round(1)
    st.bar_chart(bf_by_season, x="season", y="bat_first_win_rate")

    # Phase 3 addition: upcoming IPL matches from CricketData
    st.divider()
    st.subheader("Upcoming IPL matches")
    try:
        upcoming_df = load_upcoming_matches()
        if upcoming_df.empty:
            st.info("No upcoming IPL matches in the current fixtures data.")
        else:
            st.dataframe(upcoming_df, use_container_width=True)
    except Exception as exc:
        st.warning(f"Upcoming matches unavailable: {exc}")

    # Raw data at the bottom
    st.subheader("Recent matches (latest 20)")
    st.dataframe(df.tail(20), use_container_width=True)

    # Attribution footer — per ADR-005
    st.divider()
    st.caption(
        "Data: [Cricsheet](https://cricsheet.org) (ODbL). "
        "This project uses data from Cricsheet, made available under the ODbL."
    )


if __name__ == "__main__":
    main()
