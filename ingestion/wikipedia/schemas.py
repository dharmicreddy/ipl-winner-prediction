"""Pydantic models for the Wikipedia REST summary response.

We only model the fields we use. Wikipedia's summary endpoint returns
a fairly stable structure documented at:
https://en.wikipedia.org/api/rest_v1/#/Page%20content/get_page_summary__title_
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lat: float
    lon: float


class ContentUrls(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page: str


class ContentUrlsWrapper(BaseModel):
    model_config = ConfigDict(extra="ignore")
    desktop: ContentUrls


class WikipediaSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str
    description: str | None = None
    extract: str | None = None
    coordinates: Coordinates | None = None
    content_urls: ContentUrlsWrapper | None = None

    def get_wikipedia_url(self) -> str | None:
        return self.content_urls.desktop.page if self.content_urls else None
