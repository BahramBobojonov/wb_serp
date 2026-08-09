from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable
from uuid import UUID

from .batch import BatchWindow


DDL = (
    "CREATE SCHEMA IF NOT EXISTS serp",
    """
    CREATE TABLE IF NOT EXISTS serp.batches (
        batch_id text PRIMARY KEY,
        batch_started_at_local timestamptz NOT NULL,
        batch_started_at_utc timestamptz NOT NULL,
        batch_timezone text NOT NULL,
        status text NOT NULL,
        queries_expected integer NOT NULL,
        queries_completed integer NOT NULL,
        pages_expected integer NOT NULL,
        pages_completed integer NOT NULL,
        product_rows integer NOT NULL,
        error_count integer NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS serp.products (
        batch_id text NOT NULL REFERENCES serp.batches(batch_id) ON DELETE CASCADE,
        query text NOT NULL,
        dest_label text NOT NULL,
        dest text,
        page integer NOT NULL,
        position_on_page integer NOT NULL,
        global_position integer,
        total_catalog bigint,
        normquery text,
        catalog_type text,
        catalog_value text,
        nm_id bigint,
        root bigint,
        name text,
        brand text,
        brand_id bigint,
        supplier text,
        supplier_id bigint,
        subject_id bigint,
        rating numeric,
        review_rating numeric,
        feedbacks integer,
        price_rub numeric(14,2),
        basic_price_rub numeric(14,2),
        discount_percent numeric(8,2),
        sizes_count integer,
        option_ids text,
        colors text,
        total_quantity integer,
        time1 integer,
        time2 integer,
        wh integer,
        view_flags bigint,
        is_advert boolean NOT NULL DEFAULT false,
        page_fetched_at timestamptz,
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (batch_id, query, dest_label, page, position_on_page)
    )
    """,
    "ALTER TABLE serp.products ADD COLUMN IF NOT EXISTS page_fetched_at timestamptz",
    "CREATE INDEX IF NOT EXISTS serp_products_nm_batch_idx ON serp.products (nm_id, batch_id)",
    "CREATE INDEX IF NOT EXISTS serp_products_query_batch_idx ON serp.products (query, batch_id)",
    "CREATE INDEX IF NOT EXISTS serp_batches_started_idx ON serp.batches (batch_started_at_utc)",
    """
    CREATE TABLE IF NOT EXISTS serp.query_totals (
        batch_id text NOT NULL REFERENCES serp.batches(batch_id) ON DELETE CASCADE,
        query text NOT NULL,
        dest_label text NOT NULL,
        products_collected integer NOT NULL,
        pages_collected integer NOT NULL,
        total_catalog bigint,
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (batch_id, query, dest_label)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS serp.attempts (
        attempt_id uuid PRIMARY KEY,
        batch_id text NOT NULL REFERENCES serp.batches(batch_id) ON DELETE CASCADE,
        started_at timestamptz NOT NULL,
        finished_at timestamptz NOT NULL,
        status text NOT NULL,
        pages_completed_before integer NOT NULL,
        pages_completed_after integer NOT NULL,
        error_count integer NOT NULL,
        errors jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
)


PRODUCT_COLUMNS = (
    "batch_id", "query", "dest_label", "dest", "page", "position_on_page",
    "global_position", "total_catalog", "normquery", "catalog_type", "catalog_value",
    "nm_id", "root", "name", "brand", "brand_id", "supplier", "supplier_id",
    "subject_id", "rating", "review_rating", "feedbacks", "price_rub",
    "basic_price_rub", "discount_percent", "sizes_count", "option_ids", "colors",
    "total_quantity", "time1", "time2", "wh", "view_flags", "is_advert", "page_fetched_at",
)


def _integer(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


INTEGER_PRODUCT_COLUMNS = {
    "page", "position_on_page", "global_position", "total_catalog", "nm_id", "root",
    "brand_id", "supplier_id", "subject_id", "feedbacks", "sizes_count",
    "total_quantity", "time1", "time2", "wh", "view_flags",
}
DECIMAL_PRODUCT_COLUMNS = {"rating", "review_rating", "price_rub", "basic_price_rub", "discount_percent"}


def _product_values(row: dict) -> tuple:
    values = []
    for column in PRODUCT_COLUMNS:
        source_key = {
            "brand_id": "brandId",
            "supplier_id": "supplierId",
            "subject_id": "subjectId",
            "review_rating": "reviewRating",
            "total_quantity": "totalQuantity",
            "view_flags": "viewFlags",
        }.get(column, column)
        value = row.get(source_key)
        if column in INTEGER_PRODUCT_COLUMNS:
            value = _integer(value)
        elif column in DECIMAL_PRODUCT_COLUMNS:
            value = _decimal(value)
        elif column == "is_advert":
            value = str(value).lower() in {"1", "true", "yes"}
        elif value is not None:
            value = str(value)
        values.append(value)
    return tuple(values)


class PostgresStore:
    def __init__(self, database_url: str, *, connect: Callable | None = None) -> None:
        if not database_url.strip():
            raise ValueError("DATABASE_URL is required")
        self.database_url = database_url
        self._connect = connect

    def _open(self):
        if self._connect is not None:
            return self._connect(self.database_url)
        import psycopg

        return psycopg.connect(self.database_url)

    def acquire_collector_lease(self, lock_key: int = 864209739) -> object | None:
        connection = self._open()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))
                acquired = bool(cursor.fetchone()[0])
            if acquired:
                return connection
        except Exception:
            connection.close()
            raise
        connection.close()
        return None

    @staticmethod
    def release_collector_lease(connection: object, lock_key: int = 864209739) -> None:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
        finally:
            connection.close()

    def publish(
        self,
        *,
        batch: BatchWindow,
        attempt_id: UUID,
        attempt_started_at: datetime,
        attempt_finished_at: datetime,
        status: str,
        queries_expected: int,
        pages_expected: int,
        pages_completed_before: int,
        rows: list[dict],
        totals: list[dict],
        errors: list[dict],
        retention_days: int = 90,
    ) -> None:
        pages_completed_after = sum(int(row.get("pages_collected") or 0) for row in totals)
        connection = self._open()
        try:
            with connection.cursor() as cursor:
                for statement in DDL:
                    cursor.execute(statement)
                cursor.execute(
                    """
                    INSERT INTO serp.batches (
                        batch_id, batch_started_at_local, batch_started_at_utc, batch_timezone,
                        status, queries_expected, queries_completed, pages_expected,
                        pages_completed, product_rows, error_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (batch_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        queries_expected = EXCLUDED.queries_expected,
                        queries_completed = EXCLUDED.queries_completed,
                        pages_expected = EXCLUDED.pages_expected,
                        pages_completed = EXCLUDED.pages_completed,
                        product_rows = EXCLUDED.product_rows,
                        error_count = EXCLUDED.error_count,
                        updated_at = now()
                    """,
                    (
                        batch.batch_id, batch.started_at_local, batch.started_at_utc, batch.timezone,
                        status, queries_expected, len(totals), pages_expected,
                        pages_completed_after, len(rows), len(errors),
                    ),
                )
                cursor.execute(
                    "DELETE FROM serp.batches WHERE batch_started_at_utc < now() - (%s * interval '1 day')",
                    (retention_days,),
                )
                if rows:
                    columns = ", ".join(PRODUCT_COLUMNS)
                    placeholders = ", ".join(["%s"] * len(PRODUCT_COLUMNS))
                    updates = ", ".join(
                        f"{column} = EXCLUDED.{column}"
                        for column in PRODUCT_COLUMNS
                        if column not in {"batch_id", "query", "dest_label", "page", "position_on_page"}
                    )
                    cursor.executemany(
                        f"""
                        INSERT INTO serp.products ({columns}) VALUES ({placeholders})
                        ON CONFLICT (batch_id, query, dest_label, page, position_on_page) DO UPDATE SET
                            {updates}, updated_at = now()
                        """,
                        [_product_values(row) for row in rows],
                    )
                if totals:
                    cursor.executemany(
                        """
                        INSERT INTO serp.query_totals (
                            batch_id, query, dest_label, products_collected, pages_collected, total_catalog
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (batch_id, query, dest_label) DO UPDATE SET
                            products_collected = EXCLUDED.products_collected,
                            pages_collected = EXCLUDED.pages_collected,
                            total_catalog = EXCLUDED.total_catalog,
                            updated_at = now()
                        """,
                        [
                            (
                                batch.batch_id,
                                row["query"],
                                row["dest_label"],
                                int(row.get("products_collected") or 0),
                                int(row.get("pages_collected") or 0),
                                _integer(row.get("total_catalog")),
                            )
                            for row in totals
                        ],
                    )
                cursor.execute(
                    """
                    INSERT INTO serp.attempts (
                        attempt_id, batch_id, started_at, finished_at, status,
                        pages_completed_before, pages_completed_after, error_count, errors
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        attempt_id, batch.batch_id, attempt_started_at, attempt_finished_at, status,
                        pages_completed_before, pages_completed_after, len(errors),
                        json.dumps(errors, ensure_ascii=False),
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
