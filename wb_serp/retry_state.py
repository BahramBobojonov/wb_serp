from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def curl_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(run_root: Path) -> Path:
    return run_root / "retry_state.json"


def should_defer(run_root: Path, current_hash: str, *, now: datetime, retry_after_seconds: int) -> bool:
    try:
        state = json.loads(_path(run_root).read_text(encoding="utf-8"))
        blocked_at = datetime.fromisoformat(state["blocked_at_utc"])
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return False
    age = (now.astimezone(UTC) - blocked_at.astimezone(UTC)).total_seconds()
    return state.get("curl_sha256") == current_hash and age < retry_after_seconds


def mark_blocked(run_root: Path, current_hash: str, *, now: datetime) -> None:
    path = _path(run_root)
    path.write_text(json.dumps({"curl_sha256": current_hash, "blocked_at_utc": now.astimezone(UTC).isoformat()}, indent=2), encoding="utf-8")


def clear(run_root: Path) -> None:
    _path(run_root).unlink(missing_ok=True)


def is_complete(run_root: Path) -> bool:
    try:
        manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return manifest.get("status") == "complete"
