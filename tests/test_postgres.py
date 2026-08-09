from datetime import UTC, datetime
from uuid import UUID

import pytest

from wb_serp.batch import BatchWindow
from wb_serp.postgres import PostgresStore


class RecordingCursor:
    def __init__(self, fail_on: str = "") -> None:
        self.fail_on = fail_on
        self.executed: list[tuple[str, object]] = []
        self.executed_many: list[tuple[str, list[tuple]]] = []
        self.fetchone_value = (True,)

    def execute(self, sql: str, params=None) -> None:
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("database write failed")
        self.executed.append((sql, params))

    def executemany(self, sql: str, params) -> None:
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("database write failed")
        self.executed_many.append((sql, list(params)))

    def fetchone(self):
        return self.fetchone_value

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class RecordingConnection:
    def __init__(self, fail_on: str = "") -> None:
        self.cursor_instance = RecordingCursor(fail_on)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self) -> RecordingCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def batch() -> BatchWindow:
    return BatchWindow(
        batch_id="serp_20260810_0500",
        started_at_local=datetime.fromisoformat("2026-08-10T05:00:00+05:00"),
        started_at_utc=datetime(2026, 8, 10, 0, 0, tzinfo=UTC),
        timezone="Asia/Yekaterinburg",
    )


def product_row() -> dict:
    return {
        "batch_id": "serp_20260810_0500",
        "query": "linen tulle",
        "dest_label": "main",
        "dest": "-5818883",
        "page": 1,
        "position_on_page": 1,
        "global_position": 1,
        "total_catalog": 1000,
        "nm_id": "123",
        "name": "Tulle",
        "brand": "Brand",
        "price_rub": 1500.5,
        "basic_price_rub": 2000,
        "discount_percent": 24.98,
        "is_advert": "0",
    }


def test_publish_creates_schema_and_upserts_one_batch_snapshot_and_attempt() -> None:
    connection = RecordingConnection()
    store = PostgresStore("postgresql://unused", connect=lambda _: connection)

    store.publish(
        batch=batch(),
        attempt_id=UUID("00000000-0000-0000-0000-000000000001"),
        attempt_started_at=datetime(2026, 8, 10, 0, 1, tzinfo=UTC),
        attempt_finished_at=datetime(2026, 8, 10, 0, 2, tzinfo=UTC),
        status="complete",
        queries_expected=739,
        pages_expected=1478,
        pages_completed_before=0,
        rows=[product_row()],
        totals=[{"query": "linen tulle", "dest_label": "main", "products_collected": 1, "pages_collected": 2, "total_catalog": 1000}],
        errors=[],
    )

    statements = "\n".join(sql for sql, _ in connection.cursor_instance.executed)
    many_statements = "\n".join(sql for sql, _ in connection.cursor_instance.executed_many)
    assert "CREATE SCHEMA IF NOT EXISTS serp" in statements
    assert "INSERT INTO serp.batches" in statements
    assert "ON CONFLICT (batch_id) DO UPDATE" in statements
    assert "INSERT INTO serp.attempts" in statements
    assert "page_fetched_at" in statements
    assert "DELETE FROM serp.batches" in statements
    assert "INSERT INTO serp.products" in many_statements
    assert "ON CONFLICT (batch_id, query, dest_label, page, position_on_page) DO UPDATE" in many_statements
    assert "INSERT INTO serp.query_totals" in many_statements
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.closed is True


def test_collector_lease_uses_session_advisory_lock_until_release() -> None:
    connection = RecordingConnection()
    store = PostgresStore("postgresql://unused", connect=lambda _: connection)
    lease = store.acquire_collector_lease()
    assert lease is connection
    assert connection.closed is False
    store.release_collector_lease(lease)
    statements = "\n".join(sql for sql, _ in connection.cursor_instance.executed)
    assert "pg_try_advisory_lock" in statements
    assert "pg_advisory_unlock" in statements
    assert connection.closed is True


def test_publish_rolls_back_when_product_upsert_fails() -> None:
    connection = RecordingConnection(fail_on="INSERT INTO serp.products")
    store = PostgresStore("postgresql://unused", connect=lambda _: connection)

    with pytest.raises(RuntimeError, match="database write failed"):
        store.publish(
            batch=batch(),
            attempt_id=UUID("00000000-0000-0000-0000-000000000002"),
            attempt_started_at=datetime(2026, 8, 10, 0, 1, tzinfo=UTC),
            attempt_finished_at=datetime(2026, 8, 10, 0, 2, tzinfo=UTC),
            status="blocked",
            queries_expected=1,
            pages_expected=2,
            pages_completed_before=1,
            rows=[product_row()],
            totals=[],
            errors=[{"query": "linen tulle", "page": 2, "status": 498}],
        )

    assert connection.committed is False
    assert connection.rolled_back is True
    assert connection.closed is True
