"""Time helpers. Everything that needs 'now' goes through here so tests can patch it."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_frozen: datetime | None = None


def freeze(moment: datetime | None) -> None:
    """Test hook: pin (or with None, release) the clock."""
    global _frozen
    _frozen = moment


def now_utc() -> datetime:
    return _frozen or datetime.now(UTC)


def get_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return ZoneInfo("Asia/Kolkata")


def today_in(tz_name: str) -> date:
    """'Today' in the given timezone, never the server's."""
    return now_utc().astimezone(get_tz(tz_name)).date()
