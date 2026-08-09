from datetime import UTC, datetime, timedelta

from wb_serp.retry_state import clear, curl_hash, is_complete, mark_blocked, should_defer


def test_same_blocked_curl_waits_30_minutes_but_changed_curl_does_not(tmp_path):
    curl_file = tmp_path / "curl.txt"
    curl_file.write_text("old", encoding="utf-8")
    old_hash = curl_hash(curl_file)
    now = datetime(2026, 8, 10, tzinfo=UTC)
    mark_blocked(tmp_path, old_hash, now=now)
    assert should_defer(tmp_path, old_hash, now=now + timedelta(minutes=29), retry_after_seconds=1800)
    assert not should_defer(tmp_path, "new-hash", now=now + timedelta(minutes=1), retry_after_seconds=1800)
    assert not should_defer(tmp_path, old_hash, now=now + timedelta(minutes=30), retry_after_seconds=1800)
    clear(tmp_path)
    assert not should_defer(tmp_path, old_hash, now=now, retry_after_seconds=1800)


def test_complete_manifest_is_detected(tmp_path):
    (tmp_path / "run_manifest.json").write_text('{"status":"complete"}', encoding="utf-8")
    assert is_complete(tmp_path)
