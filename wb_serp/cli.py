from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from .client import CurlClient, parse_curl_template
from .config import load_queries
from .input_file import materialize_curl_file
from .pipeline import CollectionBlocked, collect, write_outputs


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resumable WB SERP collector for Railway")
    parser.add_argument("--config", default=os.getenv("WB_CONFIG_FILE", "/app/config/search_growth_focus.yaml"))
    parser.add_argument("--curl-file", default=os.getenv("WB_CURL_FILE", "/data/input/wb_curl.txt"))
    parser.add_argument("--data-dir", default=os.getenv("WB_DATA_DIR", "/data"))
    parser.add_argument("--run-name", default=os.getenv("WB_RUN_NAME", f"serp_{datetime.now():%Y%m%d}"))
    parser.add_argument("--pages", type=int, default=_env_int("WB_PAGES", 2))
    parser.add_argument("--dest", default=os.getenv("WB_DEST", "-5818883"))
    parser.add_argument("--dest-label", default=os.getenv("WB_DEST_LABEL", "main"))
    parser.add_argument("--sleep-seconds", type=float, default=_env_float("WB_SLEEP_SECONDS", 6.0))
    parser.add_argument("--query-limit", type=int, default=_env_int("WB_QUERY_LIMIT", 0))
    parser.add_argument("--check-config", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queries = load_queries(Path(args.config))
    if args.query_limit > 0:
        queries = queries[: args.query_limit]
    print(f"queries={len(queries)} pages={args.pages} run_name={args.run_name}")
    if args.check_config:
        return 0

    curl_path = materialize_curl_file(Path(args.curl_file), os.getenv("WB_CURL_B64", ""))
    if not curl_path.exists():
        print(f"curl file not found: {curl_path}", file=sys.stderr)
        return 3
    run_root = Path(args.data_dir) / "runs" / args.run_name
    run_root.mkdir(parents=True, exist_ok=True)
    client = CurlClient(parse_curl_template(curl_path))
    errors: list[dict] = []
    try:
        errors = collect(
            client,
            queries,
            run_root,
            pages=args.pages,
            dest=args.dest,
            dest_label=args.dest_label,
            sleep_seconds=args.sleep_seconds,
        )
    except CollectionBlocked as exc:
        errors = exc.errors
        write_outputs(run_root, queries, errors, status="blocked")
        print(f"collection stopped: {exc}", file=sys.stderr)
        return 2
    write_outputs(run_root, queries, errors, status="complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
