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

## Time fields and outputs

The batch start is stored in both local and UTC ISO-8601 form. The run manifest
contains `batch_started_at_local` and `batch_started_at_utc`. Product and query
total CSV rows contain `batch_started_at_local`, providing a stable snapshot key
for a later database loader.

Existing output locations remain unchanged under
`/data/runs/<batch-name>/public/`. Database ingestion is outside this change.

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

## Verification

Automated tests cover boundary mapping, same-batch hourly mapping, day rollover,
explicit run-name override, timestamp propagation to manifest/CSV, and the
existing checkpoint resume behavior. A Railway smoke run verifies that two
hourly executions in one batch share checkpoints, while an execution in the
next batch starts fresh.
