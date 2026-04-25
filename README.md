# IPL Winner Prediction

End-to-end data engineering pipeline for IPL match prediction. Built on **licensed open data and official APIs only** — no Terms-of-Service compromises. Demonstrates ingestion, warehousing, transformation, ML, and serving on free-tier tooling.

**Status:** Phase 3 — Incremental API ingestion (complete). Next: Phase 4 — dbt warehouse.

## Quick start

```bash
# 1. Copy env template and adjust if needed
cp .env.example .env

# 2. Bring up Postgres
docker compose -f docker/docker-compose.yml --env-file .env up -d

# 3. Create a virtualenv and install
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# 4. Apply DB migrations
python -m ingestion.db.migrate

# 5. Download & load Cricsheet data (2022–2024 by default)
python -m ingestion.cricsheet.downloader
python -m ingestion.cricsheet.bronze_loader
python -m ingestion.cricsheet.silver_parser

# 6. Fetch Wikipedia venue metadata (CC BY-SA)
python -m ingestion.wikipedia.venue_client
python -m ingestion.wikipedia.venue_parser

# 7. Fetch upcoming fixtures from CricketData.org (requires API key in .env)
python -m ingestion.cricketdata.fixtures_client
python -m ingestion.cricketdata.fixtures_parser

# 8. Launch the dashboard
streamlit run dashboard/app.py

## Why this project

IPL is a good modeling target: abundant open historical data, clear binary outcomes per match, strong seasonal effects, and a tournament structure that rewards probability calibration. This project is intentionally built on licensed open data and official APIs only — every source has a documented legal basis; see `docs/data-sources.md`. Most IPL-prediction portfolios on GitHub scrape sources that prohibit automated access; this one does not.

## Architecture

```mermaid
flowchart LR
    A1[Cricsheet<br/>historical, ODbL] --> B[Bronze<br/>raw snapshots]
    A2[Wikipedia<br/>venue metadata] --> B
    A3[CricketData.org<br/>optional, fixtures] --> B
    B --> C[Silver<br/>cleaned]
    C --> D[Gold<br/>star schema]
    D --> F[Features]
    F --> M[XGBoost<br/>+ calibration]
    M --> S[Streamlit<br/>dashboard]
    GHA[GitHub Actions<br/>weekly cron] -.orchestrates.-> B
    GHA -.-> C
    GHA -.-> M
```

**Read path:** sources -> bronze -> silver -> gold -> features -> model -> dashboard.
**Orchestration:** GitHub Actions runs the pipeline weekly. Airflow DAGs exist locally for demonstration.

## dbt warehouse

The data warehouse is built via [dbt](https://www.getdbt.com/) with all models defined in `warehouse/`. Run `dbt build --project-dir warehouse` to rebuild silver and gold layers, run all data tests, and load the team-canonical seed.

![dbt lineage graph](docs/img/dbt_lineage.png)

**Layers:**
- **silver_raw** (Python-populated): typed rows ingested from Cricsheet, Wikipedia, and CricketData.org
- **silver** (dbt views): cleaned views over silver_raw, source for the gold layer
- **gold** (dbt views): analytical models with derived columns (e.g. `batting_first_won`), entity-resolved teams via the `team_canonical` seed, and a star schema (`fact_matches`, `fact_ball_by_ball`, `dim_teams`, `dim_venues`, `dim_players`)

A snapshot model (`warehouse/snapshots/dim_teams_snapshot.sql`) tracks team rebrandings (e.g. "Royal Challengers Bangalore" → "Royal Challengers Bengaluru") with SCD Type 2 semantics. To explore model documentation interactively: `dbt docs generate --project-dir warehouse && dbt docs serve --project-dir warehouse`.

## Tech stack

| Layer | Choice |
|---|---|
| Ingestion | Python + httpx (API / bulk download only) |
| Warehouse | PostgreSQL (Docker local, Neon free optional) |
| Transformation | dbt Core |
| ML | scikit-learn -> XGBoost + calibration, MLflow tracking |
| Orchestration | GitHub Actions (prod) + Airflow (local demo) |
| Dashboard | Streamlit Community Cloud |
| CI | GitHub Actions |

See the ADRs in `docs/decisions/` for the rationale behind each choice.

## Repository layout

```
ipl-winner-prediction/
├── README.md
├── docs/
│   ├── problem-definition.md
│   ├── data-sources.md
│   └── decisions/            # ADRs
├── ingestion/                # Phase 2+
├── warehouse/                # dbt project, Phase 4
├── features/                 # Phase 5
├── models/                   # Phase 6
├── dashboard/                # Streamlit app, Phase 8
├── orchestration/            # Airflow DAGs + GH Actions workflows
├── tests/
├── docker/
├── .github/workflows/
├── pyproject.toml
└── .env.example
```

## Roadmap

| Phase | Focus | Status |
|---|---|---|
| 1 | Discovery & design | Complete |
| 2 | Historical backfill (Cricsheet) | Complete |
| 3 | Incremental API ingestion | Complete |
| 4 | dbt warehouse | Next |
| 5 | Feature engineering | Pending |
| 6 | Modeling + calibration | Pending |
| 7 | Orchestration | Pending |
| 8 | Dashboard + write-up | Pending |

End of Phase 2: a thin end-to-end vertical slice — one season loaded, one gold view, one Streamlit page locally.

## Attribution

- Historical match data: [Cricsheet](https://cricsheet.org) — licensed under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/1-0/).
- Venue metadata: [Wikipedia](https://en.wikipedia.org) — CC BY-SA 4.0.
- Upcoming fixtures: [CricketData.org](https://cricketdata.org) — used per their published terms of service.

## License

Code: MIT. Derived data retains the license of its source (Cricsheet: ODbL; Wikipedia: CC BY-SA).
