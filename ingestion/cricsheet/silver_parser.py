"""Silver parser for Cricsheet data.

Reads bronze.cricsheet_matches, parses each JSON via pydantic models,
upserts to silver_raw.matches and silver_raw.deliveries.

Super-over deliveries are skipped (innings where super_over=True).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from psycopg.types.json import Json

from ingestion.cricsheet.schemas import CricsheetMatch, Delivery, Innings, MatchInfo
from ingestion.db.connection import get_connection

logger = logging.getLogger(__name__)


MATCH_UPSERT_SQL = """
    INSERT INTO silver_raw.matches (
        match_id, season, match_date, venue, city,
        team_home, team_away, toss_winner, toss_decision,
        winner, win_margin_type, win_margin, method,
        player_of_match, officials, raw_ingested_at
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (match_id) DO UPDATE SET
        season           = EXCLUDED.season,
        match_date       = EXCLUDED.match_date,
        venue            = EXCLUDED.venue,
        city             = EXCLUDED.city,
        team_home        = EXCLUDED.team_home,
        team_away        = EXCLUDED.team_away,
        toss_winner      = EXCLUDED.toss_winner,
        toss_decision    = EXCLUDED.toss_decision,
        winner           = EXCLUDED.winner,
        win_margin_type  = EXCLUDED.win_margin_type,
        win_margin       = EXCLUDED.win_margin,
        method           = EXCLUDED.method,
        player_of_match  = EXCLUDED.player_of_match,
        officials        = EXCLUDED.officials,
        raw_ingested_at  = EXCLUDED.raw_ingested_at,
        parsed_at        = now()
"""

DELIVERIES_DELETE_SQL = "DELETE FROM silver_raw.deliveries WHERE match_id = %s"

DELIVERIES_INSERT_SQL = """
    INSERT INTO silver_raw.deliveries (
        match_id, innings, over_number, ball_in_over,
        batting_team, bowling_team,
        batter, non_striker, bowler,
        runs_batter, runs_extras, runs_total,
        extras_type, wicket_kind, player_out
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def parse_match_row(match_id: str, raw_content: dict[str, Any], raw_ingested_at) -> dict[str, Any]:
    """Parse a single bronze row into silver match + deliveries payload."""
    match = CricsheetMatch.from_json(raw_content)
    info = match.info

    match_record = _build_match_record(match_id, info, raw_ingested_at)
    delivery_records = _build_delivery_records(match_id, match.innings, info.teams)
    return {"match": match_record, "deliveries": delivery_records}


def _build_match_record(match_id: str, info: MatchInfo, raw_ingested_at) -> tuple:
    """Flatten a MatchInfo into a tuple matching MATCH_UPSERT_SQL."""
    team_home, team_away = info.teams[0], info.teams[1]
    winner = info.outcome.winner

    win_margin_type: str | None = None
    win_margin: int | None = None
    if info.outcome.by:
        if info.outcome.by.runs is not None:
            win_margin_type, win_margin = "runs", info.outcome.by.runs
        elif info.outcome.by.wickets is not None:
            win_margin_type, win_margin = "wickets", info.outcome.by.wickets

    officials_json = Json(info.officials.model_dump()) if info.officials else None
    player_of_match = info.player_of_match[0] if info.player_of_match else None

    return (
        match_id,
        str(info.season),
        info.dates[0],
        info.venue,
        info.city,
        team_home,
        team_away,
        info.toss.winner,
        info.toss.decision,
        winner,
        win_margin_type,
        win_margin,
        info.outcome.method,
        player_of_match,
        officials_json,
        raw_ingested_at,
    )


def _build_delivery_records(
    match_id: str, innings_list: list[Innings], teams: list[str]
) -> list[tuple]:
    """Expand innings → overs → deliveries into flat rows. Skips super overs."""
    rows: list[tuple] = []
    team_home, team_away = teams[0], teams[1]

    for innings_idx, innings in enumerate(innings_list, start=1):
        if innings.super_over:
            continue  # Phase 2 simplification

        batting_team = innings.team
        bowling_team = team_away if batting_team == team_home else team_home

        for over in innings.overs:
            for ball_idx, delivery in enumerate(over.deliveries, start=1):
                rows.append(
                    _build_delivery_row(
                        match_id,
                        innings_idx,
                        over.over,
                        ball_idx,
                        batting_team,
                        bowling_team,
                        delivery,
                    )
                )
    return rows


def _build_delivery_row(
    match_id: str,
    innings_idx: int,
    over_num: int,
    ball_idx: int,
    batting_team: str,
    bowling_team: str,
    delivery: Delivery,
) -> tuple:
    extras_type = next(iter(delivery.extras.keys()), None)
    first_wicket = delivery.wickets[0] if delivery.wickets else None
    return (
        match_id,
        innings_idx,
        over_num,
        ball_idx,
        batting_team,
        bowling_team,
        delivery.batter,
        delivery.non_striker,
        delivery.bowler,
        delivery.runs.batter,
        delivery.runs.extras,
        delivery.runs.total,
        extras_type,
        first_wicket.kind if first_wicket else None,
        first_wicket.player_out if first_wicket else None,
    )


def parse_bronze_to_silver(limit: int | None = None) -> dict[str, int]:
    """Parse every bronze row into silver_raw. Returns counts.

    Args:
        limit: if set, parse only the first N bronze rows (useful for testing).

    Returns:
        {"matches": N, "deliveries": M, "errors": K}
    """
    query = (
        "SELECT match_id, raw_content, ingested_at FROM bronze.cricsheet_matches ORDER BY match_id"
    )
    if limit:
        query += f" LIMIT {int(limit)}"

    matches_written = 0
    deliveries_written = 0
    errors = 0

    with get_connection() as conn:
        with conn.cursor() as read_cur:
            read_cur.execute(query)
            bronze_rows = read_cur.fetchall()

        logger.info("Parsing %d bronze rows into silver_raw", len(bronze_rows))

        with conn.cursor() as write_cur:
            for match_id, raw_content, ingested_at in bronze_rows:
                # psycopg returns jsonb as a Python dict already.
                payload_dict = (
                    raw_content if isinstance(raw_content, dict) else json.loads(raw_content)
                )
                try:
                    parsed = parse_match_row(match_id, payload_dict, ingested_at)
                except Exception as exc:
                    logger.warning("Failed to parse match %s: %s", match_id, exc)
                    errors += 1
                    continue

                write_cur.execute(MATCH_UPSERT_SQL, parsed["match"])
                # Delete + insert deliveries to keep idempotency simple.
                write_cur.execute(DELIVERIES_DELETE_SQL, (match_id,))
                if parsed["deliveries"]:
                    write_cur.executemany(DELIVERIES_INSERT_SQL, parsed["deliveries"])

                matches_written += 1
                deliveries_written += len(parsed["deliveries"])

    logger.info(
        "Silver parse complete: %d matches, %d deliveries, %d errors",
        matches_written,
        deliveries_written,
        errors,
    )
    return {"matches": matches_written, "deliveries": deliveries_written, "errors": errors}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = parse_bronze_to_silver()
    print(
        f"Parsed {result['matches']} matches, "
        f"{result['deliveries']} deliveries ({result['errors']} errors)"
    )
