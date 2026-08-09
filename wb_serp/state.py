import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _page_path(root: Path, query: str, page: int) -> Path:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
    return root / "pages" / digest / f"page_{page:03d}.json"


def save_page(root: Path, query: str, page: int, rows: list[dict], total: Any, *, fetched_at_utc: str | None = None) -> Path:
    path = _page_path(root, query, page)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "query": query,
        "page": page,
        "total": total,
        "fetched_at_utc": fetched_at_utc or datetime.now(UTC).isoformat(),
        "rows": rows,
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def load_page(root: Path, query: str, page: int) -> dict | None:
    path = _page_path(root, query, page)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("query") != query or payload.get("page") != page or not isinstance(payload.get("rows"), list):
        return None
    return payload


def merge_pages(root: Path, queries: list[str]) -> tuple[list[dict], list[dict]]:
    all_rows: list[dict] = []
    totals: list[dict] = []
    for query in queries:
        query_rows: list[dict] = []
        pages: list[int] = []
        totals_seen: list[int] = []
        page = 1
        while True:
            payload = load_page(root, query, page)
            if payload is None:
                break
            fetched_at = payload.get("fetched_at_utc")
            query_rows.extend([{**row, "page_fetched_at": fetched_at} for row in payload["rows"]])
            pages.append(page)
            try:
                totals_seen.append(int(payload.get("total") or 0))
            except (TypeError, ValueError):
                pass
            page += 1
        if pages:
            all_rows.extend(query_rows)
            totals.append(
                {
                    "query": query,
                    "products_collected": len(query_rows),
                    "pages_collected": len(pages),
                    "total_catalog": max(totals_seen or [0]),
                }
            )
    return all_rows, totals
