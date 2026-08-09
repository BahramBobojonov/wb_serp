from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from wb_serp import cli


class SuccessfulClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str]] = []

    def fetch(self, query: str, page: int, dest: str):
        self.calls.append((query, page, dest))
        return 200, {"data": {"total": 1, "products": [{"id": 123, "sizes": []}]}}, ""


class BlockedClient:
    def fetch(self, query: str, page: int, dest: str):
        return 498, None, "blocked"


class RecordingStore:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.published: list[dict] = []

    def publish(self, **kwargs) -> None:
        if self.fail:
            raise RuntimeError("postgres unavailable")
        self.published.append(kwargs)


def inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    config = tmp_path / "queries.yaml"
    config.write_text("focus_queries:\n  core:\n    - linen tulle\n", encoding="utf-8")
    curl_file = tmp_path / "wb_curl.txt"
    curl_file.write_text("curl placeholder", encoding="utf-8")
    return config, curl_file, tmp_path / "data"


def args(config: Path, curl_file: Path, data_dir: Path, *extra: str) -> list[str]:
    return [
        "--config", str(config),
        "--curl-file", str(curl_file),
        "--data-dir", str(data_dir),
        "--pages", "2",
        "--sleep-seconds", "0",
        *extra,
    ]


def test_hourly_cli_attempts_share_batch_checkpoints_and_publish_two_attempts(tmp_path: Path, monkeypatch) -> None:
    config, curl_file, data_dir = inputs(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    store = RecordingStore()
    clients: list[SuccessfulClient] = []

    def client_factory(_path: Path) -> SuccessfulClient:
        client = SuccessfulClient()
        clients.append(client)
        return client

    now = datetime(2026, 8, 10, 6, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
    first = cli.main(args(config, curl_file, data_dir), now=now, store_factory=lambda _: store, client_factory=client_factory)
    second = cli.main(args(config, curl_file, data_dir), now=now.replace(hour=7), store_factory=lambda _: store, client_factory=client_factory)

    assert first == 0
    assert second == 0
    assert clients[0].calls == [("linen tulle", 1, "-5818883"), ("linen tulle", 2, "-5818883")]
    assert clients[1].calls == []
    assert [call["batch"].batch_id for call in store.published] == ["serp_20260810_0500", "serp_20260810_0500"]
    assert [call["pages_completed_before"] for call in store.published] == [0, 2]


def test_cli_publishes_blocked_attempt_before_returning_two(tmp_path: Path, monkeypatch) -> None:
    config, curl_file, data_dir = inputs(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    store = RecordingStore()

    result = cli.main(
        args(config, curl_file, data_dir, "--run-name", "manual_smoke"),
        now=datetime(2026, 8, 10, 6, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg")),
        store_factory=lambda _: store,
        client_factory=lambda _: BlockedClient(),
    )

    assert result == 2
    assert store.published[0]["status"] == "blocked"
    assert store.published[0]["batch"].batch_id == "manual_smoke"
    assert store.published[0]["errors"][0]["status"] == 498


def test_cli_returns_four_when_database_publication_fails(tmp_path: Path, monkeypatch) -> None:
    config, curl_file, data_dir = inputs(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")

    result = cli.main(
        args(config, curl_file, data_dir),
        now=datetime(2026, 8, 10, 6, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg")),
        store_factory=lambda _: RecordingStore(fail=True),
        client_factory=lambda _: SuccessfulClient(),
    )

    assert result == 4
