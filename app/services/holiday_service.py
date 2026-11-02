import datetime as dt
import uuid

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import Pagination
from app.core.errors import conflict, not_found
from app.models import Holiday
from app.models import User
from app.schemas import HolidayCreate
from app.services.common import count


def _out(h: Holiday) -> dict:
    return {
        "id": h.id,
        "holiday_date": h.holiday_date,
        "label": h.label,
        "is_global": h.owner_id is None,
    }


def list_holidays(db: Session, user: User, year: int | None, page: Pagination) -> dict:
    base = select(Holiday).where(or_(Holiday.owner_id.is_(None), Holiday.owner_id == user.id))
    if year:
        base = base.where(Holiday.holiday_date.between(dt.date(year, 1, 1), dt.date(year, 12, 31)))
    rows = db.scalars(
        base.order_by(Holiday.holiday_date, Holiday.owner_id.asc().nulls_first())
        .limit(page.limit)
        .offset(page.offset)
    )
    return {
        "items": [_out(h) for h in rows],
        "total": count(db, base),
        "limit": page.limit,
        "offset": page.offset,
    }


def add_holiday(db: Session, user: User, data: HolidayCreate) -> dict:
    exists = db.scalar(
        select(Holiday.id).where(
            Holiday.holiday_date == data.holiday_date,
            or_(Holiday.owner_id.is_(None), Holiday.owner_id == user.id),
        )
    )
    if exists:
        raise conflict(
            "A holiday is already listed on this date.", {"holiday_date": "Already listed."}
        )
    h = Holiday(owner_id=user.id, holiday_date=data.holiday_date, label=data.label)
    db.add(h)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict(
            "A holiday is already listed on this date.", {"holiday_date": "Already listed."}
        ) from exc
    return _out(h)


def delete_holiday(db: Session, user: User, holiday_id: uuid.UUID) -> None:
    h = db.scalar(select(Holiday).where(Holiday.id == holiday_id, Holiday.owner_id == user.id))
    if h is None:  # also covers global (read-only) holidays and other users' rows
        raise not_found("Holiday not found.")
    db.delete(h)
    db.commit()
