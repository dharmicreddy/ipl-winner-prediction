"""Unit tests for the Wikipedia venue parser."""

from __future__ import annotations

import json
from pathlib import Path

from ingestion.wikipedia.schemas import WikipediaSummary
from ingestion.wikipedia.venue_parser import parse_venue

FIXTURE = Path(__file__).parent.parent / "fixtures" / "wikipedia_wankhede.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_pydantic_accepts_real_response():
    body = _load_fixture()
    summary = WikipediaSummary.model_validate(body)
    assert summary.title
    # Wankhede has coordinates
    assert summary.coordinates is not None


def test_parse_venue_produces_nine_columns():
    body = _load_fixture()
    row = parse_venue(
        response_id=1,
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Wankhede_Stadium",
        body=body,
        content_sha256="a" * 64,
    )
    assert len(row) == 9
    assert row[0] == "Wankhede_Stadium"  # wiki_title extracted from URL
    assert row[1]  # display_title populated


def test_handles_missing_coordinates():
    # Simulate a response without coordinates (like Eden Gardens)
    body_no_coords = {
        "title": "Eden Gardens",
        "description": "Cricket ground",
        "extract": "Eden Gardens is...",
    }
    row = parse_venue(
        response_id=99,
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Eden_Gardens",
        body=body_no_coords,
        content_sha256="b" * 64,
    )
    assert row[4] is None  # latitude
    assert row[5] is None  # longitude
