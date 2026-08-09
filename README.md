# WB SERP for Railway

Standalone, resumable collection of Wildberries public search results. It uses
the current `focus_queries` YAML contract and produces compact CSV files
compatible with the existing competitor and price reports.

## Railway smoke test

1. Deploy this repository as a Railway service.
2. Add a Volume mounted at `/data`.
3. Upload a fresh Chrome-exported curl:

   ```powershell
   railway volume files upload "$HOME\Downloads\wb_curl.txt" /input/wb_curl.txt
   ```

4. Set variables:

   ```text
   WB_PAGES=2
   WB_QUERY_LIMIT=1
   WB_RUN_NAME=smoke_20260809
   WB_CURL_FILE=/data/input/wb_curl.txt
   WB_DATA_DIR=/data
   ```

5. Run the service manually. Success is HTTP `200` with rows in
   `/data/runs/<run-name>/public/serp_products.csv`.

After the smoke test, set `WB_QUERY_LIMIT=0`. Reusing the same `WB_RUN_NAME`
continues from saved page checkpoints. A `401`, `403`, `429`, `498`, HTML, or
invalid JSON response exits non-zero and keeps all completed pages.

## Local checks

```powershell
$env:PYTHONPATH="."
pytest -q tests
python -m wb_serp.cli --config config/search_growth_focus.yaml --check-config
```

Never commit `wb_curl.txt` or Google credentials. The next optional step is to
sync the extension output folder through Google Drive and download the current
file into `/data/input` before collection.
