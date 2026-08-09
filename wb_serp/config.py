from pathlib import Path
from typing import Any

import yaml


def _strings(value: Any):
    if isinstance(value, str):
        text = value.strip()
        if text:
            yield text
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)


def load_queries(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    if not isinstance(data, dict) or "focus_queries" not in data:
        raise ValueError("YAML must contain focus_queries")
    result: list[str] = []
    seen: set[str] = set()
    for query in _strings(data["focus_queries"]):
        key = query.casefold()
        if key not in seen:
            seen.add(key)
            result.append(query)
    if not result:
        raise ValueError("focus_queries contains no queries")
    return result
