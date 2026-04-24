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
    """Pull upcoming IPL fixtures from dbt-built silver.

    Phase 4 temporary: queries silver.silver__fixtures directly. Will switch
    to gold.upcoming_ipl_matches once rebuilt via dbt in Chunk 4.3.
    """
    query = """
        SELECT match_date, team_1, team_2, venue, status, series_name
        FROM silver.silver__fixtures
        WHERE is_ipl = true
          AND (status IS NULL OR status NOT ILIKE '%won by%')
        ORDER BY match_date
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn)


@st.cache_data(ttl=300)
def load_matches() -> pd.DataFrame:
    """Pull completed matches from the dbt-built silver layer.

    Phase 4 temporary: queries silver.silver__matches directly. Will switch
    to gold.fact_matches once it's rebuilt via dbt in Chunk 4.3.
    """
    query = """
        SELECT season, match_date, venue, city,
               team_home, team_away, toss_winner, toss_decision,
               winner, win_margin_type, win_margin
        FROM silver.silver__matches
        WHERE winner IS NOT NULL
        ORDER BY match_date
    """
    with get_connection() as conn:
        return pd.read_sql(query, conn)


def main() -> None:
    st.title("🏏 IPL Prediction — Phase 2 Vertical Slice")
    st.caption(
        "Thin end-to-end slice. Data sourced from Cricsheet (ODbL). "
        "Phase 8 will replace this with the real dashboard."
    )

    df = load_matches()
    if df.empty:
        st.warning("No matches in gold.fact_matches. Run the pipeline first.")
        return

    # Top-level stats
    col1, col2, col3 = st.columns(3)
    col1.metric("Matches loaded", f"{len(df):,}")
    col2.metric("Seasons", df["season"].nunique())
    col3.metric("Bat-first win %", "—", help="Rebuilt via dbt in Chunk 4.3")

    st.divider()

    # Matches by season — the "thin slice" chart
    st.subheader("Matches by season")
    by_season = df.groupby("season").size().reset_index(name="matches")
    st.bar_chart(by_season, x="season", y="matches")

    # Bat-first-by-season chart returns once dbt rebuilds gold.fact_matches (Chunk 4.3).

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
