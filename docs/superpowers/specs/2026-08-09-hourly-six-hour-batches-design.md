# Hourly retries for six-hour SERP batches

## Goal

Collect a fresh complete snapshot of all YAML queries every six hours while
running Railway every hour so failed or unfinished pages are retried promptly.

## Batch identity

Batch boundaries use `Asia/Yekaterinburg`: `05:00`, `11:00`, `17:00`, and
`23:00`. Every hourly invocation maps deterministically to the latest boundary.
For example, invocations from `05:00` through `10:59` use
`serp_YYYYMMDD_0500`.

The next boundary always creates a new batch. Therefore successful queries from
the preceding six-hour batch never suppress collection in the new batch.

## Resume behavior

Railway runs at minute zero of every hour. All invocations inside one batch use
the same volume directory and page checkpoints. Completed pages are skipped;
missing and failed pages are requested again. Before every invocation the
service downloads the current private curl file from Google Drive.

Blocked authentication or throttling errors end the invocation without deleting
checkpoints. The next hourly invocation in the same batch resumes from them.

## Time fields and file outputs

The batch start is stored in both local and UTC ISO-8601 form. The run manifest
contains `batch_started_at_local` and `batch_started_at_utc`. Product and query
total CSV rows contain `batch_started_at_local`, providing a stable snapshot key
for a later database loader.

Existing output locations remain unchanged under
`/data/runs/<batch-name>/public/`.

## PostgreSQL history

The collector uses the existing Railway PostgreSQL service from the
`optimistic-emotion` project through a secret `DATABASE_URL`. It creates a
dedicated `serp` schema and does not modify the existing finance, raw, staging,
mart, or report schemas.

### `serp.batches`

One row represents one six-hour snapshot. `batch_id` is the primary key and
matches the automatic run name. The row also stores local and UTC batch time,
timezone, current status, expected and completed query/page counts, product row
count, error count, and created/updated timestamps.

### `serp.products`

This table stores the normalized searchable product fields already emitted to
CSV: query, destination, page and positions, catalogue metadata, `nm_id`, name,
brand, supplier, subject, ratings, feedback count, product/basic price,
discount, quantity, delivery fields, flags, and advertising marker. The primary
key is `(batch_id, query, dest_label, page, position_on_page)`. A repeated hourly
attempt therefore upserts the same positions instead of creating duplicates.

### `serp.query_totals`

One row per `(batch_id, query, dest_label)` stores collected products/pages and
the catalogue total. Rows are upserted as pages are completed.

### `serp.attempts`

Every hourly Railway invocation receives a unique attempt ID. It stores its
batch ID, start/finish time, final status, page counts before and after the
attempt, error count, and error details as JSONB. This records operational retry
history without duplicating the six-hour market snapshot.

## Database publication behavior

After file outputs are rebuilt, the application publishes the current merged
batch state in one PostgreSQL transaction. A blocked WB request still publishes
all completed pages and the failed attempt before returning a non-zero exit
code. If PostgreSQL publication fails, page checkpoints remain on the volume and
the invocation returns non-zero; the next hourly invocation skips fetched pages
and retries publication.

Schema creation and all writes are idempotent. Historical batches are never
deleted or overwritten by later six-hour batches.

## Configuration

- Railway cron: `0 * * * *`.
- Default timezone: `Asia/Yekaterinburg`, overridable with `WB_BATCH_TIMEZONE`.
- Default local anchor hour: `05:00`, overridable with
  `WB_BATCH_ANCHOR_HOUR`.
- Default batch width: six hours. Thus `00:00` through `04:59` belongs to the
  preceding calendar day's `23:00` batch; no additional mutable state is
  required.
- An explicit `WB_RUN_NAME` or `--run-name` continues to override automatic
  batch naming for smoke tests and manual diagnostics.
- `DATABASE_URL` is required in Railway and is stored as a sealed service
  variable.

## Verification

Automated tests cover boundary mapping, same-batch hourly mapping, day rollover,
explicit run-name override, timestamp propagation to manifest/CSV, PostgreSQL
DDL and idempotent upserts, database failure behavior, and the existing
checkpoint resume behavior. An integration check runs against the existing
PostgreSQL service. A Railway smoke run verifies that two hourly executions in
one batch share checkpoints, while an execution in the next batch starts fresh.
