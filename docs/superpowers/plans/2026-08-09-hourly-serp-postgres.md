# Hourly SERP Batches and PostgreSQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run every hour, resume one deterministic six-hour SERP batch, and persist each batch plus hourly attempts in PostgreSQL.

**Architecture:** A focused `batch.py` derives the current Yekaterinburg batch without mutable state. Existing checkpoints remain the source of resume behavior. A focused `postgres.py` owns schema creation and transactional idempotent publication after CSV/manifest generation.

**Tech Stack:** Python 3.13, `zoneinfo`, psycopg 3, PostgreSQL, pytest, Railway cron and volume.

## Global Constraints

- Batch timezone is `Asia/Yekaterinburg` with local boundaries `05:00`, `11:00`, `17:00`, `23:00`.
- Railway invokes the collector at minute zero every hour.
- Every new six-hour batch collects every YAML query again.
- Hourly attempts inside a batch reuse page checkpoints and skip completed pages.
- PostgreSQL uses the existing service through sealed `DATABASE_URL` and only creates or writes the `serp` schema.
- Explicit `WB_RUN_NAME` continues to override automatic naming.

---

### Task 1: Deterministic six-hour batch identity

**Files:**
- Create: `wb_serp/batch.py`
- Create: `tests/test_batch.py`
- Modify: `wb_serp/cli.py`

**Interfaces:**
- Produces: `BatchWindow(batch_id: str, started_at_local: datetime, started_at_utc: datetime, timezone: str)`.
- Produces: `current_batch(now: datetime | None = None, timezone_name: str = "Asia/Yekaterinburg", anchor_hour: int = 5, width_hours: int = 6) -> BatchWindow`.

- [ ] Write table-driven failing tests with literal expected IDs for `05:00`, `10:59`, `11:00`, `23:00`, and `02:00` mapping to the preceding day's `23:00` batch.
- [ ] Run `python -m pytest -q tests/test_batch.py` and verify failure because `wb_serp.batch` does not exist.
- [ ] Implement `BatchWindow` and anchor-relative floor arithmetic using `zoneinfo.ZoneInfo`; format IDs as `serp_YYYYMMDD_HHMM`.
- [ ] Change CLI argument default to `None`, then resolve `WB_RUN_NAME`/`--run-name` or `current_batch()` after argument parsing.
- [ ] Run `python -m pytest -q tests/test_batch.py tests/test_config.py` and commit.

### Task 2: Propagate batch time into files

**Files:**
- Modify: `wb_serp/pipeline.py`
- Modify: `tests/test_pipeline.py`

**Interfaces:**
- Changes: `write_outputs(..., status: str, batch: BatchWindow) -> tuple[list[dict], list[dict], dict]`.
- Returns the exact product rows, query totals, and manifest later published to PostgreSQL.

- [ ] Write a failing test using a literal `BatchWindow` and assert `batch_started_at_local` in both CSV files plus local/UTC timestamps in `run_manifest.json`.
- [ ] Run the focused test and verify the missing-argument/output failure.
- [ ] Add batch fields without changing existing SERP columns; return `(rows, totals, manifest)`.
- [ ] Run `python -m pytest -q tests/test_pipeline.py` and commit.

### Task 3: Idempotent PostgreSQL store

**Files:**
- Create: `wb_serp/postgres.py`
- Create: `tests/test_postgres.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `PostgresStore(database_url: str)`.
- Produces: `publish(batch: BatchWindow, attempt_id: UUID, attempt_started_at: datetime, attempt_finished_at: datetime, status: str, queries_expected: int, pages_expected: int, rows: list[dict], totals: list[dict], errors: list[dict]) -> None`.

- [ ] Write failing tests against a recording DB-API connection that exercise real SQL generation and transaction boundaries: schema/table creation, batch upsert, product upsert key, totals upsert, and attempt insertion.
- [ ] Run `python -m pytest -q tests/test_postgres.py` and verify failure because the module is absent.
- [ ] Implement `ensure_schema()` with `CREATE SCHEMA IF NOT EXISTS serp` and four `CREATE TABLE IF NOT EXISTS` statements matching the approved spec.
- [ ] Implement `publish()` with `executemany` and `ON CONFLICT DO UPDATE`; serialize error details with psycopg JSONB adaptation; commit once and roll back on failure.
- [ ] Add `psycopg[binary]==3.2.9` to `requirements.txt`.
- [ ] Run `python -m pytest -q tests/test_postgres.py` and commit.

### Task 4: CLI attempt lifecycle and failure behavior

**Files:**
- Modify: `wb_serp/cli.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: `current_batch`, `write_outputs`, and `PostgresStore.publish`.
- Behavior: every non-check invocation requires `DATABASE_URL`, publishes complete or blocked output, and exits non-zero if DB publication fails.

- [ ] Write failing CLI tests with temporary YAML/curl/checkpoints and a fake store factory: successful publication, blocked partial publication, explicit run-name override, and database error returning exit code `4`.
- [ ] Run `python -m pytest -q tests/test_cli.py` and verify expected failures.
- [ ] Refactor `main()` so batch/attempt metadata is created once, output is always rebuilt after controlled collection outcomes, DB publication happens before the final exit code, and `--check-config` remains DB-independent.
- [ ] Run `python -m pytest -q tests/test_cli.py tests/test_pipeline.py tests/test_postgres.py` and commit.

### Task 5: Railway schedule, documentation, and integration

**Files:**
- Modify: `railway.json`
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Railway cron becomes `0 * * * *`.
- Runtime consumes `DATABASE_URL`, `WB_BATCH_TIMEZONE`, and `WB_BATCH_ANCHOR_HOUR`.

- [ ] Change cron to hourly and document the four local batch boundaries, hourly resume semantics, Postgres tables, and safe variables.
- [ ] Run the full local suite: `python -m pytest -q tests`.
- [ ] Connect to the existing PostgreSQL using its public URL only inside the process environment; run schema creation and a rollback-safe test batch, then query only row counts and keys.
- [ ] Set sealed `DATABASE_URL` on `wb_serp`, push commits, and verify the Railway build succeeds.
- [ ] Run a one-query explicit smoke batch twice and verify first `FETCH`, second `SKIP`, one batch row, two attempt rows, and no duplicated product keys.
- [ ] Remove the explicit smoke run variable, restore `WB_QUERY_LIMIT=0`, and confirm the next cron is hourly.
