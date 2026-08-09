# WB SERP for Railway

Standalone, resumable collection of Wildberries public search results from the
`focus_queries` YAML contract. It writes compact CSV files, keeps page
checkpoints on a Railway volume, and persists historical batches in PostgreSQL.

## Production schedule

Railway runs at minute zero every hour. With `Asia/Yekaterinburg` and anchor
hour `5`, full market batches begin at `05:00`, `11:00`, `17:00`, and `23:00`.
Attempts inside one window share a name such as `serp_20260810_0500`: completed
pages are skipped and only missing pages retry. The next boundary receives a
new batch ID and collects every YAML query again.

Required runtime variables:

```text
WB_CONFIG_FILE=/app/config/search_growth_focus.yaml
WB_CURL_FILE=/data/input/wb_curl.txt
WB_DATA_DIR=/data
WB_BATCH_TIMEZONE=Asia/Yekaterinburg
WB_BATCH_ANCHOR_HOUR=5
WB_PAGES=2
WB_QUERY_LIMIT=0
DATABASE_URL=<sealed PostgreSQL connection URL>
GOOGLE_DRIVE_CURL_FILE_ID=<private Drive file ID>
GOOGLE_CREDENTIALS_B64=<base64 service-account JSON>
```

Do not set `WB_RUN_NAME` in production. It is only a manual smoke-test override.

## PostgreSQL history

The collector creates and writes only the `serp` schema:

- `serp.batches` — one row per six-hour snapshot;
- `serp.products` — query positions, cards, and prices;
- `serp.query_totals` — completeness and catalogue totals by query;
- `serp.attempts` — each hourly retry and its errors.

Writes are idempotent. If database publication fails, volume checkpoints remain
and the next hourly attempt republishes them without refetching successful
pages.

## Files and resume

Outputs remain under `/data/runs/<batch-id>/`:

```text
public/serp_products.csv
public/query_totals.csv
collection_errors.csv
run_manifest.json
pages/<query-hash>/page_NNN.json
```

A `401`, `403`, `429`, `498`, HTML, or invalid JSON response exits non-zero and
keeps every completed checkpoint.

## Private Google Drive refresh

Share only `wb_curl.txt` with the service-account email. Before every hourly
attempt Railway downloads the latest private file into `/data/input`.

On Windows, `windows/install_sync_task.ps1` installs a hidden logon task that
copies only `Downloads/wb_curl.txt` to `G:/Мой диск/WB_SERP_SYNC` whenever the
Chrome extension refreshes it. Normal Chrome downloads are unaffected.

## Smoke test

Temporarily set `WB_QUERY_LIMIT=1` and `WB_RUN_NAME=smoke_<timestamp>`, then use
Railway **Run now** twice. The first execution must log `FETCH`; the second must
log `SKIP ... checkpoint exists`. Remove `WB_RUN_NAME` and restore
`WB_QUERY_LIMIT=0` afterwards.

## Local checks

```powershell
$env:PYTHONPATH="."
python -m pytest -q tests
python -m wb_serp.cli --config config/search_growth_focus.yaml --check-config
```

Never commit `wb_curl.txt`, Google credentials, or `DATABASE_URL`.
