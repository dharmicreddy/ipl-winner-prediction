"""IPL prediction full pipeline DAG.

Phase 7 / Issue #6.

Stages (built incrementally across Chunks 7.1 and 7.2):
    Chunk 7.1: ingest tasks (this commit)
        db_migrate -> cricsheet_download -> cricsheet_load_bronze -> cricsheet_parse_silver
                                       -> wikipedia_fetch -> wikipedia_parse
                                       -> cricketdata_fetch -> cricketdata_parse
    Chunk 7.2: extends with dbt + features + train + calibrate
    Chunk 7.3+: GitHub Actions parity

Entrypoints are invoked via BashOperator subprocesses to ensure clean Python
state per task. Both Airflow and the GH Actions cron call the same
`python -m ingestion.<module>` commands — no duplicate logic per Issue #6.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator

# Default task settings: retry once on transient failures (Cricsheet timeouts,
# CricketData rate limits). SLA: each task should finish within 10 minutes.
DEFAULT_ARGS = {
    "owner": "dharmicreddy",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
    "email_on_failure": False,
    "email_on_retry": False,
}

# Common context applied to every BashOperator task. The mounted project
# is at /opt/airflow/project; PYTHONPATH is already set in the env so
# `python -m ingestion.X` resolves correctly.
TASK_CWD = "/opt/airflow/project"


with DAG(
    dag_id="ipl_pipeline",
    description="End-to-end IPL pipeline: ingest -> dbt -> train -> calibrate",
    default_args=DEFAULT_ARGS,
    # Tuesday 06:00 UTC during IPL season. None = manual trigger only for now;
    # Chunk 7.3 sets this to the cron when GH Actions is also live.
    schedule=None,
    start_date=datetime(2026, 4, 1),
    catchup=False,
    max_active_runs=1,
    tags=["ipl", "phase-7", "ingest"],
) as dag:
    start = EmptyOperator(task_id="start")

    db_migrate = BashOperator(
        task_id="db_migrate",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.db.migrate",
    )

    # --- Cricsheet ingestion chain ---
    cricsheet_download = BashOperator(
        task_id="cricsheet_download",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.cricsheet.downloader",
    )

    cricsheet_load_bronze = BashOperator(
        task_id="cricsheet_load_bronze",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.cricsheet.bronze_loader",
    )

    cricsheet_parse_silver = BashOperator(
        task_id="cricsheet_parse_silver",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.cricsheet.silver_parser",
    )

    # --- Wikipedia ingestion chain ---
    wikipedia_fetch = BashOperator(
        task_id="wikipedia_fetch",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.wikipedia.venue_client",
    )

    wikipedia_parse = BashOperator(
        task_id="wikipedia_parse",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.wikipedia.venue_parser",
    )

    # --- CricketData ingestion chain ---
    cricketdata_fetch = BashOperator(
        task_id="cricketdata_fetch",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.cricketdata.fixtures_client",
    )

    cricketdata_parse = BashOperator(
        task_id="cricketdata_parse",
        bash_command=f"cd {TASK_CWD} && python -m ingestion.cricketdata.fixtures_parser",
    )

    end = EmptyOperator(task_id="end")

    # --- Dependency graph ---
    # All three source chains run in parallel after db_migrate.
    # Each chain is internally sequential (download/fetch -> load -> parse).
    start >> db_migrate

    db_migrate >> cricsheet_download >> cricsheet_load_bronze >> cricsheet_parse_silver
    db_migrate >> wikipedia_fetch >> wikipedia_parse
    db_migrate >> cricketdata_fetch >> cricketdata_parse

    [cricsheet_parse_silver, wikipedia_parse, cricketdata_parse] >> end
