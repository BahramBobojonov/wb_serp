from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from wb_serp.batch import current_batch


YEKT = ZoneInfo("Asia/Yekaterinburg")


@pytest.mark.parametrize(
    ("now", "expected_id", "expected_local", "expected_utc"),
    [
        (datetime(2026, 8, 10, 5, 0, tzinfo=YEKT), "serp_20260810_0500", "2026-08-10T05:00:00+05:00", "2026-08-10T00:00:00+00:00"),
        (datetime(2026, 8, 10, 10, 59, tzinfo=YEKT), "serp_20260810_0500", "2026-08-10T05:00:00+05:00", "2026-08-10T00:00:00+00:00"),
        (datetime(2026, 8, 10, 11, 0, tzinfo=YEKT), "serp_20260810_1100", "2026-08-10T11:00:00+05:00", "2026-08-10T06:00:00+00:00"),
        (datetime(2026, 8, 10, 23, 0, tzinfo=YEKT), "serp_20260810_2300", "2026-08-10T23:00:00+05:00", "2026-08-10T18:00:00+00:00"),
        (datetime(2026, 8, 11, 2, 0, tzinfo=YEKT), "serp_20260810_2300", "2026-08-10T23:00:00+05:00", "2026-08-10T18:00:00+00:00"),
    ],
)
def test_current_batch_maps_hourly_attempts_to_literal_six_hour_windows(
    now: datetime, expected_id: str, expected_local: str, expected_utc: str
) -> None:
    batch = current_batch(now)

    assert batch.batch_id == expected_id
    assert batch.started_at_local.isoformat() == expected_local
    assert batch.started_at_utc.isoformat() == expected_utc
    assert batch.timezone == "Asia/Yekaterinburg"
