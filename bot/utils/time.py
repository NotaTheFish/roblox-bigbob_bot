from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

def to_msk(dt: datetime) -> datetime:
    """Convert *dt* to Europe/Moscow timezone safely.

    Naive datetimes are assumed to be in UTC to preserve backward compatibility
    with timestamps stored without timezone information.
    """

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ)


__all__ = ["MOSCOW_TZ", "to_msk"]