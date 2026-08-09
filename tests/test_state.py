from pathlib import Path

import wb_serp.state as state


def test_page_checkpoint_roundtrip_and_resume(tmp_path: Path) -> None:
    assert hasattr(state, "save_page")
    assert hasattr(state, "load_page")

    rows = [{"query": "тюль лен", "page": 1, "nm_id": "123"}]
    state.save_page(tmp_path, "тюль лен", 1, rows, total=500)

    saved = state.load_page(tmp_path, "тюль лен", 1)
    assert saved == {"query": "тюль лен", "page": 1, "total": 500, "rows": rows}
    assert state.load_page(tmp_path, "тюль лен", 2) is None


def test_merge_pages_orders_by_query_then_page(tmp_path: Path) -> None:
    assert hasattr(state, "merge_pages")

    state.save_page(tmp_path, "б", 1, [{"query": "б", "page": 1, "nm_id": "3"}], total=3)
    state.save_page(tmp_path, "а", 2, [{"query": "а", "page": 2, "nm_id": "2"}], total=2)
    state.save_page(tmp_path, "а", 1, [{"query": "а", "page": 1, "nm_id": "1"}], total=2)

    rows, totals = state.merge_pages(tmp_path, ["а", "б"])
    assert [row["nm_id"] for row in rows] == ["1", "2", "3"]
    assert totals == [
        {"query": "а", "products_collected": 2, "pages_collected": 2, "total_catalog": 2},
        {"query": "б", "products_collected": 1, "pages_collected": 1, "total_catalog": 3},
    ]


def test_merge_pages_counts_successful_empty_result_as_completed_query(tmp_path: Path) -> None:
    state.save_page(tmp_path, "empty query", 1, [], total=0)

    rows, totals = state.merge_pages(tmp_path, ["empty query"])

    assert rows == []
    assert totals == [
        {"query": "empty query", "products_collected": 0, "pages_collected": 1, "total_catalog": 0}
    ]
