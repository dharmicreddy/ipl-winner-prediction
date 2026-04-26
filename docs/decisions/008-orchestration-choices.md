# ADR-008: Orchestration choices

## Status

Accepted. Phase 7 in production via GitHub Actions; Airflow runs locally.

## Context

Phase 7 wires the full pipeline (ingest → dbt → train → calibrate) for scheduled execution. ADR-001 set the high-level direction (Airflow local, GitHub Actions prod). This ADR documents the concrete sub-decisions made when actually building Phase 7.

## Decisions

### 1. LocalExecutor instead of CeleryExecutor

Airflow's reference compose file uses CeleryExecutor: webserver + scheduler + worker + Redis broker + metadata Postgres. Production teams use this so tasks can run distributed across multiple workers.

We picked LocalExecutor: webserver + scheduler + metadata Postgres. Tasks run as scheduler subprocesses on a single host.

**Trade-offs**
- ✗ Cannot demonstrate distributed task execution
- ✓ ~50 lines of compose YAML instead of ~150
- ✓ ~30 sec local boot vs. ~2 min for Celery stack
- ✓ One fewer dependency surface (Redis) that can break on Windows
- ✓ Indistinguishable from Celery in the DAG file itself

For a local demonstration of orchestration discipline, LocalExecutor is sufficient. The DAG code is identical between executors; reviewers reading `ipl_pipeline.py` cannot tell which executor will run it.

### 2. Ephemeral CI Postgres instead of hosted (Neon)

ADR-001 mentioned Neon's free tier as a possibility for production persistence. We chose ephemeral Postgres in CI (a service container that lives for the duration of one workflow run, then disappears).

**Trade-offs**
- ✗ Each scheduled run starts with a clean database; no historical state across runs
- ✗ Predictions are not persisted between runs
- ✓ Zero operational overhead — no signups, no connection strings, no secret rotation
- ✓ Each run is fully reproducible (no state pollution from prior runs)
- ✓ The pipeline's correctness is *proven* every Tuesday (any regression breaks CI)

For this project's portfolio purpose ("the pipeline runs reliably on a schedule"), ephemeral CI Postgres demonstrates orchestration discipline without the infra burden of running production storage. A real production system would graduate to Neon, RDS, or similar.

### 3. Both Airflow and GitHub Actions, not just one

We could have shipped only the GitHub Actions cron and skipped Airflow.

**Trade-off rejected: GHA only**
- ✗ Reviewers expect to see Airflow in a "data engineering portfolio" project — its absence is conspicuous
- ✗ The DAG-as-code abstraction (with retries, timeouts, dependency graphs) is valuable to demonstrate

**Trade-off rejected: Airflow only**
- ✗ Airflow needs a server. A reviewer reading the repo can't actually see the pipeline run on a schedule unless they spin up Docker locally
- ✗ "I built orchestration but it doesn't actually run anywhere" is a weaker signal than "I built orchestration and here's the green checkmark every Tuesday"

**Both:** Airflow is the discoverable artifact (clean DAG file in the repo, screenshot in README). GitHub Actions is the *actually running* schedule. Different audiences, both satisfied.

### 4. BashOperator over PythonOperator

The DAG could have used `PythonOperator` and called Python functions directly within Airflow's process. We used `BashOperator` invoking `python -m ingestion.X` instead.

**Trade-offs**
- ✗ Slightly more overhead (subprocess startup ~100ms per task)
- ✓ Each task gets a clean Python interpreter; no state leakage between tasks
- ✓ The exact same command runs locally, in Airflow, and in GitHub Actions — single source of truth
- ✓ Tasks can be debugged outside Airflow by running the bash command directly

The "same Python entrypoints in both Airflow and GHA — no duplicate logic" requirement from Issue #6 is enforced by this choice.

### 5. Read-only code mount + writable data overlay

Airflow's container needs to read our project code (`ingestion/`, `models/`, `warehouse/`) but should not modify it. Some tasks need to write data (`data/cricsheet/`, `mlruns/`, `docs/img/calibration_holdout.png`).

We use Docker volume mount layering:

```yaml
volumes:
  - ..:/opt/airflow/project:ro                                 # all code: read-only
  - ../data:/opt/airflow/project/data                          # data: writable overlay
  - ../data/mlruns:/opt/airflow/project/mlruns                 # mlruns: writable overlay
  - ../docs/img:/opt/airflow/project/docs/img                  # calibration PNG: writable
```

Plus environment variables that point dbt's writable artifacts elsewhere:

```yaml
DBT_LOG_PATH: /opt/airflow/project/data/dbt_logs
DBT_TARGET_PATH: /opt/airflow/project/data/dbt_target
```

**Why this matters:** without the read-only mount, an Airflow task could accidentally `rm -rf` or modify our source code. With it, the worst a task can do is corrupt its own data outputs — recoverable. This is defense in depth, the same principle as running production services with the minimum privilege necessary.

### 6. Cron schedule kept in DAG file but disabled in Airflow

The DAG has `schedule=None`, meaning Airflow won't auto-trigger it. Only manual triggers run the local DAG.

GitHub Actions has the actual cron (`0 6 * * 2`).

**Reasoning:** if both Airflow and GitHub Actions had the cron, they'd run redundantly. We picked GitHub Actions as the production scheduler because it runs without a local server. Airflow in this project is documentation — the DAG file *describes* a pipeline that GHA actually executes.

## Consequences

- Local demo costs ~5 min of compose-up time, after which the DAG is interactive in the Airflow UI
- Production weekly runs cost zero dollars (within GitHub free tier limits) and produce visible green checkmarks in the Actions tab
- Future orchestration changes go in one place: the DAG file. The GHA workflow YAML is essentially a pasted bash translation of the same task graph
- If we ever needed to graduate to a paid scheduler (Cloud Run Jobs, AWS Batch), the BashOperator pattern means we just translate the same `python -m ingestion.X` commands into a different runtime

## References

- [ADR-001: Hosting and orchestration](001-hosting-and-orchestration.md)
- Issue #6 — Phase 7 acceptance criteria
- `orchestration/airflow/dags/ipl_pipeline.py`
- `.github/workflows/weekly_pipeline.yml`
- `docker/airflow-compose.yml`
