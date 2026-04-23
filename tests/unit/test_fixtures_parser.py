"""Unit tests for the CricketData.org fixtures parser."""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.cricketdata.fixtures_parser import (
    _extract_series_name,
    _is_ipl,
    parse_match,
)
from ingestion.cricketdata.schemas import CricketDataResponse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "cricketdata_current_matches.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_pydantic_accepts_real_response():
    body = _load_fixture()
    response = CricketDataResponse.model_validate(body)
    assert response.status == "success"
    assert len(response.data) > 0


def test_parse_match_produces_11_columns():
    body = _load_fixture()
    response = CricketDataResponse.model_validate(body)
    match = response.data[0]
    row = parse_match(response_id=42, match=match)
    assert len(row) == 11
    assert row[0] == match.id  # fixture_id
    assert row[10] == 42  # raw_response_id


def test_ipl_detection():
    assert _is_ipl("Team A vs Team B, 5th Match, Indian Premier League 2026")
    assert _is_ipl("IPL 2024 Final")
    assert not _is_ipl("Nepal vs UAE, 2nd T20I, UAE tour of Nepal 2026")
    assert not _is_ipl("ICC World Cup 2026, Semi-final")


def test_series_name_extraction():
    assert _extract_series_name("A vs B, 1st Match, Series Name 2026") == "Series Name 2026"
    assert _extract_series_name("Solo string") == "Solo string"
    assert _extract_series_name("A vs B") == "A vs B"  # no commas -> whole string returned
