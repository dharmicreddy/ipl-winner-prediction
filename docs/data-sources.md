# Data Sources Audit

## Guiding principle

Every data source used in this project must have an **explicit, affirmative legal basis** — an open-data license, a published API ToS that permits our usage pattern, or data we maintain ourselves. Ambiguous ToS and "everyone else scrapes it" are not acceptable bases. This is both a legal discipline and a portfolio signal.

## Approved sources

### 1. Cricsheet — PRIMARY

- **What:** Ball-by-ball data for all IPL matches since 2008 (~1,200 matches), plus global cricket.
- **Format:** JSON or CSV bulk downloads; single zip per tournament.
- **License:** Open Database License (ODbL) v1.0. Grants: share, create, adapt. Requires: attribution, share-alike on derivative databases, keep-open.
- **Cadence:** Matches typically published within 1-3 days of completion. Sufficient for weekly refresh.
- **Access pattern:** HTTPS GET of the published zip URLs. No rate limits published; we fetch at most weekly and cache to bronze.
- **Attribution:** "This project uses data from Cricsheet (cricsheet.org), made available under the ODbL." — in README and dashboard footer.

### 2. Wikipedia — SUPPLEMENTARY

- **What:** Venue metadata (capacity, city, opening date, pitch characteristics where documented).
- **Access:** Wikipedia REST API (`en.wikipedia.org/api/rest_v1/`). Official, documented, rate-limited to 200 req/s per IP.
- **License:** CC BY-SA 4.0 for article text. Derived structured data requires attribution and share-alike.
- **Cadence:** Static metadata; refreshed on a slow cadence (monthly at most).

### 3. CricketData.org (free tier) — OPTIONAL, for upcoming-fixtures only

- **What:** Upcoming IPL fixtures with match keys, venues, scheduled times.
- **License:** Published Terms of Use; requires free registration for reasonable latency.
- **Cadence:** Once per weekly run.
- **Only used if we enable the "predict next match" dashboard feature.** Alternative: maintain `fixtures.yaml` in the repo manually.

### 4. Self-maintained reference data

- **What:** Team metadata (short codes, colors, current home venue), manually curated.
- **Location:** `ingestion/reference/teams.yaml`, `ingestion/reference/fixtures.yaml` (optional).
- **License:** MIT, ours.

## Explicitly rejected sources

Listed here so the decision is documented and visible to reviewers.

| Source | Why rejected |
|---|---|
| ESPNCricinfo | Terms of Use explicitly prohibit high-volume automated access. |
| Cricbuzz | No clear ToS permitting automated access; community scrapers universally disclaim commercial use. |
| iplt20.com (official IPL site) | No published developer terms or API. Content is all-rights-reserved by default. |
| Flashscore, SportsCafe, other aggregators | Same as above — no permissive license. |
| Kaggle "IPL datasets" uploaded by third parties | Unclear upstream licensing — most are themselves scrapes of ESPNCricinfo. Using them would launder the same problem. |

## Rate limits and etiquette

Even for approved sources, we follow conservative practice:

- Maximum one Cricsheet bulk fetch per week
- Exponential backoff with jitter on any HTTP error
- Caching: every successful response lands in bronze with an ingest timestamp before parsing; re-parsing never re-hits the source
- Identifiable User-Agent: `ipl-prediction/0.1 (+<repo URL>)`
- Respect `Retry-After` headers

## Attribution obligations — summary

| Source | Attribution location |
|---|---|
| Cricsheet (ODbL) | README, dashboard footer, any published derived dataset |
| Wikipedia (CC BY-SA) | README, dashboard venue view |
| CricketData.org (if used) | README, per their ToS |
