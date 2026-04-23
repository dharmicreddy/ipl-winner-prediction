"""Pydantic models for CricketData.org currentMatches responses.

We only model the fields we use. The API returns rich data but we need
just enough to populate silver.fixtures.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CricketDataMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    date: str  # "2026-04-21"
    dateTimeGMT: str | None = None  # "2026-04-21T11:15:00"
    venue: str | None = None
    status: str | None = None
    matchType: str | None = None
    teams: list[str] = []
    matchEnded: bool = False
    matchStarted: bool = False
    series_id: str | None = None


class CricketDataResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str
    data: list[CricketDataMatch] = []
