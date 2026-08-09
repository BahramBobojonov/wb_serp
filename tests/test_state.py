from pathlib import Path

import wb_serp.state as state


def test_page_checkpoint_roundtrip_and_resume(tmp_path: Path) -> None:
    rows = [{"query": "linen tulle", "page": 1, "nm_id": "123"}]
    state.save_page(tmp_path, "linen tulle", 1, rows, total=500)
    saved = state.load_page(tmp_path, "linen tulle", 1)
    assert saved["query"] == "linen tulle"
    assert saved["page"] == 1
    assert saved["total"] == 500
    assert saved["rows"] == rows
    assert saved["fetched_at_utc"]
    assert state.load_page(tmp_path, "linen tulle", 2) is None


def test_merge_pages_orders_by_query_then_page_and_exposes_fetch_time(tmp_path: Path) -> None:
    state.save_page(tmp_path, "b", 1, [{"query": "b", "page": 1, "nm_id": "3"}], total=3)
    state.save_page(tmp_path, "a", 2, [{"query": "a", "page": 2, "nm_id": "2"}], total=2)
    state.save_page(tmp_path, "a", 1, [{"query": "a", "page": 1, "nm_id": "1"}], total=2)
    rows, totals = state.merge_pages(tmp_path, ["a", "b"])
    assert [row["nm_id"] for row in rows] == ["1", "2", "3"]
    assert all(row["page_fetched_at"] for row in rows)
    assert totals == [
        {"query": "a", "products_collected": 2, "pages_collected": 2, "total_catalog": 2},
        {"query": "b", "products_collected": 1, "pages_collected": 1, "total_catalog": 3},
    ]


def test_merge_pages_counts_successful_empty_result_as_completed_query(tmp_path: Path) -> None:
    state.save_page(tmp_path, "empty query", 1, [], total=0)
    rows, totals = state.merge_pages(tmp_path, ["empty query"])
    assert rows == []
    assert totals == [
        {"query": "empty query", "products_collected": 0, "pages_collected": 1, "total_catalog": 0}
    ]
