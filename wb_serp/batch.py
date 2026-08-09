from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class BatchWindow:
    batch_id: str
    started_at_local: datetime
    started_at_utc: datetime
    timezone: str


def current_batch(
    now: datetime | None = None,
    timezone_name: str = "Asia/Yekaterinburg",
    anchor_hour: int = 5,
    width_hours: int = 6,
) -> BatchWindow:
    if not 0 <= anchor_hour <= 23:
        raise ValueError("anchor_hour must be between 0 and 23")
    if width_hours <= 0 or 24 % width_hours:
        raise ValueError("width_hours must be a positive divisor of 24")

    timezone = ZoneInfo(timezone_name)
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=UTC)
    local = instant.astimezone(timezone)
    anchor = local.replace(hour=anchor_hour, minute=0, second=0, microsecond=0)
    if local < anchor:
        anchor -= timedelta(days=1)
    elapsed_hours = int((local - anchor).total_seconds() // 3600)
    started_at_local = anchor + timedelta(hours=(elapsed_hours // width_hours) * width_hours)
    started_at_utc = started_at_local.astimezone(UTC)
    return BatchWindow(
        batch_id=f"serp_{started_at_local:%Y%m%d_%H%M}",
        started_at_local=started_at_local,
        started_at_utc=started_at_utc,
        timezone=timezone_name,
    )
