from __future__ import annotations

import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from .batch import BatchWindow
from .normalize import extract_search_payload, product_row
from .state import load_page, merge_pages, save_page


class CollectionBlocked(RuntimeError):
    def __init__(self, errors: list[dict]):
        super().__init__(errors[-1].get("error", "collection blocked"))
        self.errors = errors


def collect(client, queries: list[str], run_root: Path, *, pages: int, dest: str, dest_label: str, sleep_seconds: float) -> list[dict]:
    errors: list[dict] = []
    for query in queries:
        for page in range(1, pages + 1):
            if load_page(run_root, query, page) is not None:
                print(f"SKIP query={query!r} page={page}: checkpoint exists")
                continue
            print(f"FETCH query={query!r} page={page}")
            status, data, body = client.fetch(query, page, dest)
            if status != 200 or not isinstance(data, dict):
                error = {
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                    "query": query,
                    "page": page,
                    "dest_label": dest_label,
                    "dest": dest,
                    "status": status,
                    "error": "invalid JSON" if status == 200 else f"HTTP {status}",
                    "body_preview": (body or "")[:500],
                }
                errors.append(error)
                if status in {401, 403, 429, 498} or status == 0 or data is None:
                    raise CollectionBlocked(errors)
                continue
            products, total, metadata = extract_search_payload(data)
            rows = [
                product_row(
                    query=query,
                    dest_label=dest_label,
                    dest=dest,
                    page=page,
                    position=position,
                    product=product,
                    total=total,
                    metadata=metadata,
                )
                for position, product in enumerate(products, start=1)
                if isinstance(product, dict)
            ]
            save_page(run_root, query, page, rows, total)
            if not products:
                break
            if sleep_seconds:
                time.sleep(sleep_seconds)
    return errors


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as target:
        if not fieldnames:
            return
        writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(
    run_root: Path,
    queries: list[str],
    errors: list[dict],
    *,
    status: str,
    batch: BatchWindow,
    dest_label: str,
) -> tuple[list[dict], list[dict], dict]:
    rows, totals = merge_pages(run_root, queries)
    batch_fields = {
        "batch_id": batch.batch_id,
        "batch_started_at_local": batch.started_at_local.isoformat(),
        "batch_started_at_utc": batch.started_at_utc.isoformat(),
    }
    rows = [{**batch_fields, **row} for row in rows]
    totals = [{**batch_fields, "dest_label": dest_label, **row} for row in totals]
    _write_csv(run_root / "public" / "serp_products.csv", rows)
    _write_csv(run_root / "public" / "query_totals.csv", totals)
    _write_csv(run_root / "collection_errors.csv", errors)
    manifest = {
        "batch_id": batch.batch_id,
        "batch_started_at_local": batch.started_at_local.isoformat(),
        "batch_started_at_utc": batch.started_at_utc.isoformat(),
        "batch_timezone": batch.timezone,
        "status": status,
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "queries_expected": len(queries),
        "queries_with_data": len(totals),
        "serp_rows": len(rows),
        "errors": len(errors),
    }
    (run_root / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows, totals, manifest
