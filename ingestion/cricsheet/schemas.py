"""Pydantic models for Cricsheet match JSON.

We only model the fields we actually use. Cricsheet's JSON is rich — player
registries, match referee names, sub-second ball timings — but for match
prediction we need a much narrower slice.

If Cricsheet changes their schema, these models will raise explicit errors
at parse time rather than failing silently downstream.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Toss(BaseModel):
    model_config = ConfigDict(extra="ignore")
    winner: str
    decision: str  # "bat" or "field"


class OutcomeBy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    runs: int | None = None
    wickets: int | None = None


class Outcome(BaseModel):
    model_config = ConfigDict(extra="ignore")
    winner: str | None = None  # absent for no-results
    result: str | None = None  # "no result" | "tie" | None
    method: str | None = None  # "D/L" if rain-reduced
    by: OutcomeBy | None = None
    # eliminator is an alternate field for tied matches decided by super-over
    eliminator: str | None = None


class Officials(BaseModel):
    model_config = ConfigDict(extra="ignore")
    umpires: list[str] = Field(default_factory=list)
    tv_umpires: list[str] = Field(default_factory=list)
    reserve_umpires: list[str] = Field(default_factory=list)
    match_referees: list[str] = Field(default_factory=list)


class MatchInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    season: str | int  # sometimes int, sometimes string like "2007/08"
    dates: list[date]
    venue: str | None = None
    city: str | None = None
    teams: list[str]
    toss: Toss
    outcome: Outcome
    player_of_match: list[str] = Field(default_factory=list)
    officials: Officials | None = None


class Runs(BaseModel):
    model_config = ConfigDict(extra="ignore")
    batter: int
    extras: int
    total: int


class Wicket(BaseModel):
    model_config = ConfigDict(extra="ignore")
    player_out: str
    kind: str  # "bowled" | "caught" | "lbw" | "run out" | ...


class Delivery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    batter: str
    non_striker: str
    bowler: str
    runs: Runs
    extras: dict[str, int] = Field(default_factory=dict)  # {"wides": 1} etc.
    wickets: list[Wicket] = Field(default_factory=list)


class Over(BaseModel):
    model_config = ConfigDict(extra="ignore")
    over: int
    deliveries: list[Delivery]


class Innings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    team: str
    overs: list[Over] = Field(default_factory=list)
    super_over: bool = False


class CricsheetMatch(BaseModel):
    """Top-level Cricsheet match document."""

    model_config = ConfigDict(extra="ignore")
    info: MatchInfo
    innings: list[Innings]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> CricsheetMatch:
        return cls.model_validate(data)
