from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .batch import current_batch
from .client import CurlClient, parse_curl_template
from .config import load_queries
from .input_file import create_drive_session, download_drive_file, materialize_curl_file
from .pipeline import CollectionBlocked, CollectionTimedOut, collect, write_outputs
from .postgres import PostgresStore
from .retry_state import clear as clear_retry_state
from .retry_state import curl_hash, is_complete, mark_blocked, should_defer
from .state import load_page


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resumable WB SERP collector for Railway")
    parser.add_argument("--config", default=os.getenv("WB_CONFIG_FILE", "/app/config/search_growth_focus.yaml"))
    parser.add_argument("--curl-file", default=os.getenv("WB_CURL_FILE", "/data/input/wb_curl.txt"))
    parser.add_argument("--data-dir", default=os.getenv("WB_DATA_DIR", "/data"))
    parser.add_argument("--run-name", default=os.getenv("WB_RUN_NAME") or None)
    parser.add_argument("--pages", type=int, default=_env_int("WB_PAGES", 2))
    parser.add_argument("--dest", default=os.getenv("WB_DEST", "-5818883"))
    parser.add_argument("--dest-label", default=os.getenv("WB_DEST_LABEL", "main"))
    parser.add_argument("--sleep-seconds", type=float, default=_env_float("WB_SLEEP_SECONDS", 0.0))
    parser.add_argument("--query-limit", type=int, default=_env_int("WB_QUERY_LIMIT", 0))
    parser.add_argument("--check-config", action="store_true")
    return parser.parse_args(argv)


def _default_client_factory(curl_path: Path):
    return CurlClient(parse_curl_template(curl_path))


def _completed_pages(run_root: Path, queries: list[str], pages: int) -> int:
    return sum(
        load_page(run_root, query, page) is not None
        for query in queries
        for page in range(1, pages + 1)
    )


def main(
    argv: list[str] | None = None,
    *,
    now: datetime | None = None,
    store_factory: Callable[[str], PostgresStore] = PostgresStore,
    client_factory: Callable[[Path], object] = _default_client_factory,
) -> int:
    args = parse_args(argv)
    queries = load_queries(Path(args.config))
    if args.query_limit > 0:
        queries = queries[: args.query_limit]
    batch = current_batch(
        now,
        timezone_name=os.getenv("WB_BATCH_TIMEZONE", "Asia/Yekaterinburg"),
        anchor_hour=_env_int("WB_BATCH_ANCHOR_HOUR", 5),
    )
    if args.run_name:
        batch = replace(batch, batch_id=args.run_name)
    print(f"queries={len(queries)} pages={args.pages} run_name={batch.batch_id}")
    if args.check_config:
        return 0

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        return 5

    store = store_factory(database_url)
    lease = store.acquire_collector_lease()
    if lease is None:
        print("another collector invocation is active; skipping")
        return 0

    curl_path = Path(args.curl_file)
    run_root = Path(args.data_dir) / "runs" / batch.batch_id
    run_root.mkdir(parents=True, exist_ok=True)
    if is_complete(run_root):
        print(f"batch {batch.batch_id} is already complete; skipping")
        store.release_collector_lease(lease)
        return 0
    drive_file_id = os.getenv("GOOGLE_DRIVE_CURL_FILE_ID", "").strip()
    try:
        if drive_file_id:
            print("refreshing curl from private Google Drive file")
            session = create_drive_session(os.getenv("GOOGLE_CREDENTIALS_B64", ""))
            curl_path = download_drive_file(curl_path, drive_file_id, session)
        else:
            curl_path = materialize_curl_file(curl_path, os.getenv("WB_CURL_B64", ""))
        if not curl_path.exists():
            print(f"curl file not found: {curl_path}", file=sys.stderr)
            return 3
        current_hash = curl_hash(curl_path)
        attempt_now = (now or datetime.now(UTC)).astimezone(UTC)
        if should_defer(run_root, current_hash, now=attempt_now, retry_after_seconds=_env_int("WB_SAME_CURL_RETRY_SECONDS", 1800)):
            print("same curl was blocked recently; waiting for Drive refresh")
            return 0
        client = client_factory(curl_path)
        pages_completed_before = _completed_pages(run_root, queries, args.pages)
        attempt_started_at = attempt_now
        attempt_id = uuid4()
        errors: list[dict] = []
        status = "complete"
        exit_code = 0
        try:
            errors = collect(
                client, queries, run_root, pages=args.pages, dest=args.dest,
                dest_label=args.dest_label, sleep_seconds=args.sleep_seconds,
                deadline_monotonic=time.monotonic() + _env_int("WB_MAX_RUNTIME_SECONDS", 12600),
            )
            if errors:
                status = "partial"
                exit_code = 2
            else:
                clear_retry_state(run_root)
        except CollectionBlocked as exc:
            errors = exc.errors
            status = "blocked"
            exit_code = 2
            mark_blocked(run_root, current_hash, now=attempt_now)
            print(f"collection stopped: {exc}", file=sys.stderr)
        except CollectionTimedOut as exc:
            status = "timed_out"
            exit_code = 2
            print(f"collection stopped: {exc}", file=sys.stderr)
        rows, totals, _manifest = write_outputs(
            run_root, queries, errors, status=status, batch=batch, dest_label=args.dest_label,
        )
        attempt_finished_at = (now or datetime.now(UTC)).astimezone(UTC)
        store.publish(
            batch=batch,
            attempt_id=attempt_id,
            attempt_started_at=attempt_started_at,
            attempt_finished_at=attempt_finished_at,
            status=status,
            queries_expected=len(queries),
            pages_expected=len(queries) * args.pages,
            pages_completed_before=pages_completed_before,
            rows=rows,
            totals=totals,
            errors=errors,
            retention_days=_env_int("WB_RETENTION_DAYS", 90),
        )
        return exit_code
    except Exception as exc:
        print(f"collector failed: {exc}", file=sys.stderr)
        return 4
    finally:
        store.release_collector_lease(lease)


if __name__ == "__main__":
    raise SystemExit(main())
