# Five-minute WB block recovery design

Railway invokes the collector every five minutes. Six-hour batches remain
anchored at 05:00, 11:00, 17:00 and 23:00 Asia/Yekaterinburg. A completed batch
is a fast no-op; an incomplete batch resumes only missing page checkpoints.

The production request delay matches the actual local SERP pipeline: zero
seconds between pages and queries. On 401/403/429/498 or invalid response the
collector persists partial results and the SHA-256 of the blocked curl. The
same hash is skipped for 30 minutes, while a changed Google Drive curl retries
at the next cron tick. A 3.5-hour runtime deadline safely exits with checkpoints.

A PostgreSQL session advisory lock covers the full invocation so Railway cron
and manual Run now cannot collect concurrently. Each product records
`page_fetched_at`. Query/NM indexes support analysis, and completed batch data
is retained for 90 days. Only invocations that actually call WB create an
attempt row; lock skips, completed batches, and blocked-curl waits do not.
