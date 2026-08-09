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

   If SFTP upload is blocked, set the sealed `WB_CURL_B64` variable to the
   Base64 content of `wb_curl.txt`. The service refreshes
   `/data/input/wb_curl.txt` from this value at startup.

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

## Private Google Drive refresh

Share only the `wb_curl.txt` file with the service-account email, then set:

```text
GOOGLE_DRIVE_CURL_FILE_ID=<Drive file id>
GOOGLE_CREDENTIALS_B64=<base64 service-account JSON>
```

When both Drive variables are configured, the service downloads the latest
private file before resuming checkpoints. `WB_CURL_B64` remains a fallback.

On Windows, `windows/install_sync_task.ps1` installs a hidden logon task that
copies only `Downloads/wb_curl.txt` to `G:/Мой диск/WB_SERP_SYNC` whenever the
extension refreshes it. Normal Chrome downloads are unaffected.
