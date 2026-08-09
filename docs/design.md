# WB SERP Railway design

Standalone Railway job that reads `focus_queries` from YAML, uses a fresh WB
search curl template, and writes files compatible with the current competitor
pipeline.

## Flow

1. Chrome extension refreshes `wb_curl.txt` locally.
2. For the first deployment the curl is supplied manually; Google Drive sync is
   added only after the Railway smoke test succeeds.
3. The job reads all nested query lists under `focus_queries`, preserving order
   and removing duplicates.
4. It collects two pages per query by default and persists each successful page
   under `/data/runs/<run-name>/pages`.
5. A rerun with the same run name skips valid page checkpoints and resumes from
   the first unfinished page.
6. `403`, `429`, `498`, HTML, or invalid JSON is recorded in
   `collection_errors.csv`; the job exits non-zero without deleting completed
   checkpoints.

## Outputs

- `public/serp_products.csv`
- `public/query_totals.csv`
- `collection_errors.csv`
- `run_manifest.json`

The compact SERP columns retain the fields used by current price, competitor,
and position reports: query/destination, page/position, catalog total, nm_id,
name, brand, supplier, ratings, feedbacks, prices, stock/warehouse, and advert
flags.

## Railway

The Docker service runs as a terminating cron job. A volume mounted at `/data`
stores curl input, checkpoints, outputs, and diagnostics. Secrets are supplied
only through Railway variables or the volume and are never committed.
