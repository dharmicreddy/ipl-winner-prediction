"""As-of feature computation for the prediction page.

Replicates the dbt feature logic (warehouse/models/features/) in Python so
the dashboard can compute features for hypothetical matches.

The dbt models compute features for *known* matches in the warehouse.
The dashboard computes the same features for a *user-specified* match
(potentially in the future). Both use the same as-of cutoff:
`match_date < target_match_date`.

Per ADR-007 (no-leakage), only matches strictly before the target date
contribute to the features.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

import pandas as pd

from dashboard.lib.data import query


@dataclass
class MatchFeatures:
    """The 10 numeric features for one (hypothetical) match."""

    team_home_form_5: float | None
    team_away_form_5: float | None
    h2h_matches_played: int
    team_home_h2h_wins: int
    team_home_h2h_win_rate: float | None
    venue_matches_played: int
    venue_bat_first_win_rate: float | None
    days_since_team_home_last_match: int | None
    days_since_team_away_last_match: int | None
    match_number_in_season: int

    def to_dict(self) -> dict:
        return asdict(self)


def _load_history(target_date: date) -> pd.DataFrame:
    """Load all matches strictly before the target date."""
    df = query("""
        SELECT match_id, season, match_date, team_home, team_away,
               winner, batting_first, batting_first_won, venue
        FROM gold.fact_matches
        ORDER BY match_date
    """)
    # Coerce match_date to datetime for filtering
    df["match_date"] = pd.to_datetime(df["match_date"]).dt.date
    return df[df["match_date"] < target_date].copy()


def compute_team_form_5(history: pd.DataFrame, team: str) -> float | None:
    """Last-5-match win rate for the given team, as-of the history slice.

    Returns None if the team has no prior matches in the history.
    """
    team_matches = (
        history[(history["team_home"] == team) | (history["team_away"] == team)]
        .sort_values("match_date")
        .tail(5)
    )

    if team_matches.empty:
        return None

    team_matches = team_matches.assign(team_won=team_matches["winner"] == team)
    return float(team_matches["team_won"].mean())


def compute_h2h(
    history: pd.DataFrame, team_home: str, team_away: str
) -> tuple[int, int, float | None]:
    """Head-to-head stats between two teams, regardless of which was home/away.

    Returns (matches_played, team_home_wins, team_home_win_rate).
    """
    h2h = history[
        ((history["team_home"] == team_home) & (history["team_away"] == team_away))
        | ((history["team_home"] == team_away) & (history["team_away"] == team_home))
    ]

    matches_played = len(h2h)
    if matches_played == 0:
        return 0, 0, None

    team_home_wins = int((h2h["winner"] == team_home).sum())
    win_rate = float(team_home_wins / matches_played)
    return matches_played, team_home_wins, win_rate


def compute_venue_stats(history: pd.DataFrame, venue: str) -> tuple[int, float | None]:
    """Bat-first win rate at the given venue.

    Returns (matches_played, bat_first_win_rate).
    """
    venue_matches = history[history["venue"] == venue]
    matches_played = len(venue_matches)
    if matches_played == 0:
        return 0, None
    bat_first_rate = float(venue_matches["batting_first_won"].mean())
    return matches_played, bat_first_rate


def compute_days_since_last(history: pd.DataFrame, team: str, target_date: date) -> int | None:
    """Days between target_date and the team's most recent match."""
    team_matches = history[
        (history["team_home"] == team) | (history["team_away"] == team)
    ].sort_values("match_date")

    if team_matches.empty:
        return None

    last_date = team_matches.iloc[-1]["match_date"]
    return (target_date - last_date).days


def compute_match_number_in_season(history: pd.DataFrame, target_date: date) -> int:
    """Match number within the season containing target_date.

    The first match of the season is 1; the second is 2; etc.
    """
    season = target_date.year  # IPL seasons map roughly to calendar year
    season_matches = history[pd.to_datetime(history["match_date"]).dt.year == season]
    return len(season_matches) + 1


def compute_features(
    target_date: date,
    team_home: str,
    team_away: str,
    venue: str,
) -> MatchFeatures:
    """Compute all 10 numeric features for a hypothetical match."""
    history = _load_history(target_date)

    home_form = compute_team_form_5(history, team_home)
    away_form = compute_team_form_5(history, team_away)
    h2h_played, h2h_wins, h2h_rate = compute_h2h(history, team_home, team_away)
    venue_played, venue_rate = compute_venue_stats(history, venue)
    home_rest = compute_days_since_last(history, team_home, target_date)
    away_rest = compute_days_since_last(history, team_away, target_date)
    match_num = compute_match_number_in_season(history, target_date)

    return MatchFeatures(
        team_home_form_5=home_form,
        team_away_form_5=away_form,
        h2h_matches_played=h2h_played,
        team_home_h2h_wins=h2h_wins,
        team_home_h2h_win_rate=h2h_rate,
        venue_matches_played=venue_played,
        venue_bat_first_win_rate=venue_rate,
        days_since_team_home_last_match=home_rest,
        days_since_team_away_last_match=away_rest,
        match_number_in_season=match_num,
    )
