"""Unit tests for the Cricsheet silver parser.

These tests run against a real Cricsheet match fixture but DO NOT touch
the database. They validate the pure-Python parsing layer.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ingestion.cricsheet.schemas import CricsheetMatch
from ingestion.cricsheet.silver_parser import parse_match_row

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_match.json"


@pytest.fixture
def sample_match_raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_pydantic_parses_real_match(sample_match_raw: dict):
    """The pydantic model should accept a real Cricsheet match file."""
    match = CricsheetMatch.from_json(sample_match_raw)
    assert len(match.info.teams) == 2
    assert match.info.toss.decision in ("bat", "field")
    assert len(match.innings) >= 1  # at least one innings (rain-affected may have just one)


def test_parse_match_row_produces_expected_shape(sample_match_raw: dict):
    """parse_match_row should return match + deliveries in the right format."""
    now = datetime.now(tz=UTC)
    result = parse_match_row("test_match_1", sample_match_raw, now)

    assert set(result.keys()) == {"match", "deliveries"}
    # Match tuple should have 16 columns matching MATCH_UPSERT_SQL
    assert len(result["match"]) == 16
    assert result["match"][0] == "test_match_1"
    # Each delivery tuple should have 15 columns
    if result["deliveries"]:
        assert all(len(row) == 15 for row in result["deliveries"])


def test_deliveries_have_valid_innings_numbers(sample_match_raw: dict):
    """Innings numbers in deliveries should be 1-indexed integers."""
    now = datetime.now(tz=UTC)
    result = parse_match_row("test_match_1", sample_match_raw, now)
    innings_numbers = {row[1] for row in result["deliveries"]}
    assert innings_numbers.issubset({1, 2})  # we skip super-overs


def test_runs_total_equals_batter_plus_extras(sample_match_raw: dict):
    """Sanity check: for every delivery, total = batter + extras."""
    now = datetime.now(tz=UTC)
    result = parse_match_row("test_match_1", sample_match_raw, now)
    for row in result["deliveries"]:
        runs_batter, runs_extras, runs_total = row[9], row[10], row[11]
        assert runs_total == runs_batter + runs_extras
