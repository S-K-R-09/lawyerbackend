"""Starter global holidays (owner_id NULL) for 2026 and 2027."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Holiday

_FIXED = [
    (1, 26, "Republic Day"),
    (8, 15, "Independence Day"),
    (10, 2, "Gandhi Jayanti"),
    (12, 25, "Christmas Day"),
]
HOLIDAYS: list[tuple[date, str]] = [
    (date(year, m, d), label) for year in (2026, 2027) for m, d, label in _FIXED
]


def seed_holidays(db: Session) -> int:
    existing = set(db.scalars(select(Holiday.holiday_date).where(Holiday.owner_id.is_(None))))
    added = 0
    for day, label in HOLIDAYS:
        if day not in existing:
            db.add(Holiday(owner_id=None, holiday_date=day, label=label))
            added += 1
    db.flush()
    return added
