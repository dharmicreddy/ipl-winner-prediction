# ADR-001: Hosting and Orchestration

**Status:** Accepted
**Date:** Phase 1

## Context

Pipeline needs to run on a weekly cadence during IPL season, monthly otherwise. Budget is zero. Project is a portfolio piece — reviewers will scan the repo and dashboard.

Three realistic options:

1. **Oracle Cloud Always Free VM + Airflow 24/7.** Most "serious" look, but heavy ops for a weekly job.
2. **Local Docker + GitHub Actions cron.** Lighter, visible on the repo front page, no VM babysitting.
3. **Managed orchestrator free tier** (Prefect Cloud, Dagster Cloud). Slick, but introduces a third-party dependency and a future pricing risk.

## Decision

**Hybrid: local Docker for development, GitHub Actions scheduled workflows for production.**

Airflow is installed locally via Docker Compose. DAGs are authored and tested there. The same logical DAG is also expressed as a GitHub Actions workflow that runs on cron and executes the pipeline steps.

## Rationale

- **Cadence fit.** Running a 24/7 scheduler for a once-a-week job is wasteful and introduces failure modes (VM crashes, reboots, disk filling up) unrelated to the project.
- **Portfolio visibility.** GitHub Actions runs appear directly on the repo — green checkmarks are implicit proof the pipeline works. Airflow hidden on a VM is invisible to reviewers unless we deploy a public UI, which adds security burden.
- **Airflow skill is still demonstrated.** Local DAGs in `orchestration/airflow/dags/` show we can model dependencies, retries, and backfills. This is what reviewers actually evaluate — the DAG code — not whether it is scheduled on a cloud host.
- **Cost stability.** GitHub Actions free tier is unlimited minutes for public repos. A weekly 30-minute run is well within any threshold.

## Alternatives considered

- **Oracle Cloud + Airflow.** Rejected: ops overhead, weekly cadence does not justify a VM, failure modes unrelated to the project.
- **Prefect Cloud free tier.** Rejected: vendor lock-in for a portfolio project; pricing risk later.
- **Cron on a home machine.** Rejected: reliability and reviewer-visibility both poor.

## Consequences

- Two orchestration code paths to maintain (Airflow DAG + GitHub Actions workflow). Keep them thin — both call the same Python entrypoints.
- If the project ever grows beyond weekly cadence, we revisit and likely move production to Airflow on a VM.
- CI and production orchestration share the same platform (GitHub Actions), which means one less thing to learn and monitor.
