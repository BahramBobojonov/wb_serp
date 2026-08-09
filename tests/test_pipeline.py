import csv
from pathlib import Path

import wb_serp.pipeline as pipeline
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


def test_collect_resumes_after_existing_page_and_writes_outputs(tmp_path: Path) -> None:
    assert hasattr(pipeline, "collect")
    assert hasattr(pipeline, "write_outputs")
    run_root = tmp_path / "run"
    save_page(
        run_root,
        "тюль",
        1,
        [{"query": "тюль", "page": 1, "global_position": 1, "nm_id": "1"}],
        total=2,
    )
    fake = FakeClient()

    errors = pipeline.collect(fake, ["тюль"], run_root, pages=2, dest="-5818883", dest_label="main", sleep_seconds=0)
    pipeline.write_outputs(run_root, ["тюль"], errors, status="complete")

    assert fake.calls == [("тюль", 2, "-5818883")]
    assert errors == []
    with (run_root / "public" / "serp_products.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert [row["nm_id"] for row in rows] == ["1", "2"]
    assert (run_root / "run_manifest.json").exists()


def test_collect_stops_on_498_without_removing_checkpoints(tmp_path: Path) -> None:
    class BlockedClient:
        def fetch(self, query: str, page: int, dest: str):
            return 498, None, "blocked"

    assert hasattr(pipeline, "CollectionBlocked")
    try:
        pipeline.collect(BlockedClient(), ["тюль"], tmp_path, pages=2, dest="-1", dest_label="main", sleep_seconds=0)
    except pipeline.CollectionBlocked as exc:
        assert exc.errors[0]["status"] == 498
    else:
        raise AssertionError("498 must stop the run")
