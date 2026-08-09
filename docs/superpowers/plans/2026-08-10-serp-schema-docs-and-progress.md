# SERP Schema Documentation and Progress Logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document every PostgreSQL `serp` table and add stable query/page progress to Railway logs without changing collection behavior or stored data.

**Architecture:** `wb_serp.pipeline.collect` will derive one-based query ordinals while retaining the existing checkpoint loop and return contract. `wb_serp.cli` will print the invocation-level checkpoint summary before collection. A standalone Markdown data dictionary will mirror `wb_serp.postgres.DDL`, and README will link to it and describe real-attempt semantics.

**Tech Stack:** Python 3.13, pytest, PostgreSQL DDL, Markdown, Railway cron logs.

## Global Constraints

- Do not alter WB request construction, batching, retry state, checkpoints, PostgreSQL values, or retention.
- `remaining` is `queries_total - query_number`; it does not mean every earlier query succeeded.
- Stable ordinals follow the loaded YAML list after applying `WB_QUERY_LIMIT`.
- Work remains on `codex/serp-schema-docs-progress` until no Railway invocation is running.
- Do not use subagents.

---

### Task 1: Stable progress in collection logs

**Files:**
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_cli.py`
- Modify: `wb_serp/pipeline.py`
- Modify: `wb_serp/cli.py`

**Interfaces:**
- Consumes: `collect(client, queries, run_root, *, pages, dest, dest_label, sleep_seconds, deadline_monotonic=None)` and `_completed_pages(run_root, queries, pages) -> int`.
- Produces: unchanged `collect(...) -> list[dict]`; only stdout gains deterministic progress fields.

- [ ] **Step 1: Add failing pipeline log assertions**

Extend the two-page successful collection test to accept `capsys` and assert:

```python
output = capsys.readouterr().out
assert "FETCH query=1/1 remaining=0 page=1/2 text='query'" in output
assert "FETCH query=1/1 remaining=0 page=2/2 text='query'" in output
```

Extend the resume test to assert:

```python
assert "SKIP query=1/1 remaining=0 page=1/2 text='query': checkpoint exists" in output
```

- [ ] **Step 2: Run pipeline tests and confirm red state**

Run:

```powershell
python -m pytest -q tests/test_pipeline.py
```

Expected: assertions fail because current logs use `FETCH query='query' page=1` and `SKIP query='query' page=1`.

- [ ] **Step 3: Add query ordinals without changing the collection loop**

In `collect`, replace `for query in queries` with:

```python
queries_total = len(queries)
for query_number, query in enumerate(queries, start=1):
    remaining = queries_total - query_number
```

Use one format for both decisions:

```python
progress = (
    f"query={query_number}/{queries_total} remaining={remaining} "
    f"page={page}/{pages} text={query!r}"
)
print(f"SKIP {progress}: checkpoint exists")
print(f"FETCH {progress}")
```

Only the applicable print executes for a page.

- [ ] **Step 4: Add failing CLI startup-summary assertion**

In `test_completed_batch_is_a_fast_noop_without_second_client_or_attempt`, capture the first invocation and assert:

```python
output = capsys.readouterr().out
assert "PROGRESS queries_total=1 pages_completed=0/2" in output
```

- [ ] **Step 5: Print startup checkpoint progress**

Immediately after `pages_completed_before = _completed_pages(...)` in `cli.main`, add:

```python
print(
    f"PROGRESS queries_total={len(queries)} "
    f"pages_completed={pages_completed_before}/{len(queries) * args.pages}"
)
```

Do not print this for completed-batch, advisory-lock, or unchanged-blocked-curl no-ops because they do not enter collection.

- [ ] **Step 6: Run focused tests and commit**

Run:

```powershell
python -m pytest -q tests/test_pipeline.py tests/test_cli.py
```

Expected: all focused tests pass.

Commit:

```powershell
git add wb_serp/pipeline.py wb_serp/cli.py tests/test_pipeline.py tests/test_cli.py
git commit -m "feat: show stable SERP collection progress"
```

### Task 2: PostgreSQL SERP data dictionary

**Files:**
- Create: `docs/postgresql-serp-schema.md`
- Reference: `wb_serp/postgres.py`
- Reference: `wb_serp/batch.py`
- Reference: `wb_serp/cli.py`

**Interfaces:**
- Consumes: current `DDL`, `PRODUCT_COLUMNS`, batch-window calculation, publish/upsert behavior, and retention configuration.
- Produces: a human-readable reference only; no executable interface changes.

- [ ] **Step 1: Inventory the source-of-truth schema**

Verify the document includes exactly these tables and key relationships:

```text
serp.batches      primary key batch_id
serp.products     primary key (batch_id, query, dest_label, page, position_on_page)
serp.query_totals primary key (batch_id, query, dest_label)
serp.attempts     primary key attempt_id
```

Document that all three child tables reference `serp.batches(batch_id) ON DELETE CASCADE`.

- [ ] **Step 2: Write the complete data dictionary**

Create `docs/postgresql-serp-schema.md` with:

- schema purpose and six-hour batch lifecycle;
- one compact column table per PostgreSQL table with `column`, `type`, `meaning/source`;
- primary/foreign keys and the three indexes from `DDL`;
- upsert rules, real-attempt recording, page checkpoint relationship, and 90-day cascade retention;
- the distinction between `price_rub`, `basic_price_rub`, and `discount_percent`;
- the distinction between `position_on_page` and `global_position`;
- `page_fetched_at` as actual page acquisition time;
- warning that `updated_at` is database write time, not SERP observation time.

- [ ] **Step 3: Add compact read-only SQL examples**

Include executable examples for:

```sql
-- Latest batch status
SELECT * FROM serp.batches ORDER BY batch_started_at_utc DESC LIMIT 1;

-- One NM's positions over time
SELECT batch_started_at_utc, query, global_position, price_rub, page_fetched_at
FROM serp.products JOIN serp.batches USING (batch_id)
WHERE nm_id = :nm_id
ORDER BY batch_started_at_utc, query;

-- Failed real attempts
SELECT batch_id, started_at, status, errors
FROM serp.attempts
WHERE status <> 'complete'
ORDER BY started_at DESC;
```

Label `:nm_id` as a parameter placeholder, not literal PostgreSQL syntax for direct execution.

- [ ] **Step 4: Self-check against Python DDL and commit**

Run:

```powershell
rg -n "CREATE TABLE|CREATE INDEX|ALTER TABLE|PRODUCT_COLUMNS" wb_serp/postgres.py
rg -n "serp\.batches|serp\.products|serp\.query_totals|serp\.attempts|page_fetched_at|90" docs/postgresql-serp-schema.md
```

Expected: every DDL table, column family, index, and retention rule is represented with no undocumented table.

Commit:

```powershell
git add docs/postgresql-serp-schema.md
git commit -m "docs: add PostgreSQL SERP data dictionary"
```

### Task 3: README, full verification, and safe release

**Files:**
- Modify: `README.md`
- Verify: `railway.json`

**Interfaces:**
- Consumes: `docs/postgresql-serp-schema.md` and the progress format from Task 1.
- Produces: discoverable operational documentation and a verified main-branch release.

- [ ] **Step 1: Update README terminology and navigation**

Link `docs/postgresql-serp-schema.md` from the PostgreSQL section. Change `serp.attempts` wording from “each hourly retry” to “each invocation that actually called WB”. Add the startup and page progress examples exactly as implemented. State that completed-batch, lock, and unchanged-curl no-ops do not create attempt rows.

- [ ] **Step 2: Run all local checks**

Run:

```powershell
python -m pytest -q
python -m compileall wb_serp tests
git diff --check
git status --short
```

Expected: all tests pass, compilation succeeds, diff check is clean, and only intended README changes remain uncommitted.

- [ ] **Step 3: Commit README and push the feature branch**

```powershell
git add README.md
git commit -m "docs: link SERP schema and progress guide"
git push origin codex/serp-schema-docs-progress
```

- [ ] **Step 4: Confirm Railway has no active invocation before main push**

Use Railway status/log timestamps. Proceed only when the current cron instance is no longer `RUNNING`. If it is active, leave the feature branch pushed and wait; do not merge `main`.

- [ ] **Step 5: Fast-forward main and push once**

```powershell
git switch main
git merge --ff-only codex/serp-schema-docs-progress
git push origin main
```

Expected: one Railway deployment from the single main push.

- [ ] **Step 6: Verify production progress output**

On the next eligible cron invocation, verify logs contain:

```text
PROGRESS queries_total=739 pages_completed=<saved>/1478
FETCH query=<n>/739 remaining=<739-n> page=<p>/2 text='<query>'
```

Confirm PostgreSQL batch/page counts remain consistent and no new schema or data mutation was introduced by this release.
