import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import wb_serp.pipeline as pipeline
from wb_serp.batch import BatchWindow
from wb_serp.state import save_page


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def fetch(self, query: str, page: int, dest: str):
        self.calls.append((query, page, dest))
        return 200, {
            "data": {
                "total": 2,
                "products": [{"id": page, "sizes": [{"price": {"basic": 20000, "product": 15000}}]}],
            }
        }, ""


def fixed_batch() -> BatchWindow:
    return BatchWindow(
        batch_id="serp_20260810_0500",
        started_at_local=datetime.fromisoformat("2026-08-10T05:00:00+05:00"),
        started_at_utc=datetime(2026, 8, 10, 0, 0, tzinfo=UTC),
        timezone="Asia/Yekaterinburg",
    )


def test_collect_resumes_after_existing_page_and_writes_batch_outputs(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    save_page(
        run_root,
        "query",
        1,
        [{"query": "query", "page": 1, "global_position": 1, "nm_id": "1"}],
        total=2,
    )
    fake = FakeClient()

    errors = pipeline.collect(fake, ["query"], run_root, pages=2, dest="-5818883", dest_label="main", sleep_seconds=0)
    rows, totals, manifest = pipeline.write_outputs(
        run_root,
        ["query"],
        errors,
        status="complete",
        batch=fixed_batch(),
        dest_label="main",
    )

    assert fake.calls == [("query", 2, "-5818883")]
    assert errors == []
    with (run_root / "public" / "serp_products.csv").open(encoding="utf-8-sig", newline="") as source:
        csv_rows = list(csv.DictReader(source))
    with (run_root / "public" / "query_totals.csv").open(encoding="utf-8-sig", newline="") as source:
        csv_totals = list(csv.DictReader(source))
    saved_manifest = json.loads((run_root / "run_manifest.json").read_text(encoding="utf-8"))

    assert [row["nm_id"] for row in csv_rows] == ["1", "2"]
    assert {row["batch_id"] for row in csv_rows} == {"serp_20260810_0500"}
    assert {row["batch_started_at_local"] for row in csv_rows} == {"2026-08-10T05:00:00+05:00"}
    assert csv_totals[0]["dest_label"] == "main"
    assert csv_totals[0]["batch_started_at_local"] == "2026-08-10T05:00:00+05:00"
    assert saved_manifest["batch_started_at_local"] == "2026-08-10T05:00:00+05:00"
    assert saved_manifest["batch_started_at_utc"] == "2026-08-10T00:00:00+00:00"
    assert rows[0]["batch_id"] == "serp_20260810_0500"
    assert totals[0]["dest_label"] == "main"
    assert manifest == saved_manifest


def test_collect_stops_on_498_without_removing_checkpoints(tmp_path: Path) -> None:
    class BlockedClient:
        def fetch(self, query: str, page: int, dest: str):
            return 498, None, "blocked"

    try:
        pipeline.collect(BlockedClient(), ["query"], tmp_path, pages=2, dest="-1", dest_label="main", sleep_seconds=0)
    except pipeline.CollectionBlocked as exc:
        assert exc.errors[0]["status"] == 498
    else:
        raise AssertionError("498 must stop the run")
