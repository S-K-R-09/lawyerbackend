"""Hearing rules. This is the ONLY module that writes cases.next_hearing_date."""

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import now_utc, today_in
from app.core.deps import Pagination
from app.core.errors import conflict, validation_error
from app.models import Case
from app.models import Hearing
from app.models import User
from app.schemas import (
    OUTCOME_LABELS,
    HearingCreate,
    HearingUpdate,
    RecordHearingIn,
)
from app.services.common import count, get_owned_case, get_owned_hearing


def recompute_next_hearing(db: Session, case: Case, today: dt.date) -> dt.date | None:
    """Earliest scheduled hearing on or after `today` (the caller passes the lawyer's today)."""
    db.flush()  # sessions run with autoflush off; make pending changes visible first
    case.next_hearing_date = db.scalar(
        select(func.min(Hearing.hearing_date)).where(
            Hearing.case_id == case.id,
            Hearing.owner_id == case.owner_id,
            Hearing.status == "scheduled",
            Hearing.hearing_date >= today,
        )
    )
    return case.next_hearing_date


def _lock_case(db: Session, user: User, case_id: uuid.UUID) -> Case:
    return get_owned_case(db, user, case_id, lock=True)  # serializes hearing changes per case


def schedule_hearing(db: Session, user: User, case_id: uuid.UUID, data: HearingCreate) -> Hearing:
    case = _lock_case(db, user, case_id)
    hearing = Hearing(owner_id=user.id, case_id=case.id, **data.model_dump())
    db.add(hearing)
    recompute_next_hearing(db, case, today_in(user.timezone))
    db.commit()
    return hearing


def record_hearing(db: Session, user: User, hearing_id: uuid.UUID, data: RecordHearingIn) -> dict:
    hearing = get_owned_hearing(db, user, hearing_id)
    case = _lock_case(db, user, hearing.case_id)
    db.refresh(hearing)
    if hearing.status == "completed":
        raise conflict("This hearing is already recorded. Edit it instead.")
    if data.next_date is not None and data.next_date <= hearing.hearing_date:
        raise validation_error(
            "The next date must be after this hearing's date.",
            {"next_date": "Must be after the hearing date."},
        )

    # One transaction: complete this hearing, create the next one, refresh the denormalized date.
    hearing.status = "completed"
    hearing.outcome = data.outcome.value
    hearing.note = data.note
    hearing.recorded_at = now_utc()
    next_hearing = None
    if data.next_date is not None:
        next_hearing = Hearing(
            owner_id=user.id,
            case_id=case.id,
            hearing_date=data.next_date,
            hearing_time=data.next_time,
            purpose=data.next_purpose,
        )
        db.add(next_hearing)
    recompute_next_hearing(db, case, today_in(user.timezone))
    db.commit()

    suggest = data.outcome.value == "disposed" and case.status == "open"
    return {
        "hearing": hearing,
        "next_hearing": next_hearing,
        "case_next_hearing_date": case.next_hearing_date,
        "suggest_close_case": suggest,
        "suggestion": "Hearing marked as disposed. Do you want to close this case?"
        if suggest
        else None,
    }


def update_hearing(db: Session, user: User, hearing_id: uuid.UUID, data: HearingUpdate) -> Hearing:
    hearing = get_owned_hearing(db, user, hearing_id)
    case = _lock_case(db, user, hearing.case_id)
    db.refresh(hearing)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("hearing_date") is None:
        changes.pop("hearing_date", None)
    if changes.get("outcome") is None:
        changes.pop("outcome", None)
    if hearing.status == "scheduled" and ("outcome" in changes or "note" in changes):
        raise validation_error(
            "Record the hearing to set an outcome or note.",
            {"outcome": "Only available for recorded hearings."},
        )
    if "outcome" in changes:
        changes["outcome"] = changes["outcome"].value
    for k, v in changes.items():
        setattr(hearing, k, v)
    recompute_next_hearing(db, case, today_in(user.timezone))
    db.commit()
    return hearing


def delete_hearing(db: Session, user: User, hearing_id: uuid.UUID) -> None:
    hearing = get_owned_hearing(db, user, hearing_id)
    case = _lock_case(db, user, hearing.case_id)
    db.delete(hearing)
    recompute_next_hearing(db, case, today_in(user.timezone))
    db.commit()


def hearings_on(db: Session, user: User, day: dt.date, page: Pagination) -> dict:
    base = (
        select(Hearing, Case)
        .join(Case, Case.id == Hearing.case_id)
        .where(Hearing.owner_id == user.id, Hearing.hearing_date == day, Case.deleted_at.is_(None))
    )
    total = count(db, base)
    rows = db.execute(
        base.order_by(Hearing.hearing_time.asc().nulls_last(), Hearing.created_at, Hearing.id)
        .limit(page.limit)
        .offset(page.offset)
    ).all()
    items = [
        {
            "hearing_id": h.id,
            "case_id": c.id,
            "case_title": c.title,
            "court": c.court,
            "court_room": c.court_room,
            "time": h.hearing_time,
            "purpose": h.purpose,
            "status": h.status,
            "outcome": h.outcome,
        }
        for h, c in rows
    ]
    return {"items": items, "total": total, "limit": page.limit, "offset": page.offset}


def timeline(db: Session, user: User, case_id: uuid.UUID) -> dict:
    case = get_owned_case(db, user, case_id)
    hearings = list(
        db.scalars(select(Hearing).where(Hearing.case_id == case.id, Hearing.owner_id == user.id))
    )
    scheduled = sorted(
        (h for h in hearings if h.status == "scheduled"),
        key=lambda h: (h.hearing_date, h.hearing_time or dt.time.max),
    )
    done = sorted(
        (h for h in hearings if h.status == "completed"),
        key=lambda h: (h.hearing_date, h.recorded_at or now_utc()),
        reverse=True,
    )
    return {
        "items": [
            {
                "hearing_id": h.id,
                "date": h.hearing_date,
                "time": h.hearing_time,
                "status": h.status,
                "purpose": h.purpose,
                "outcome": h.outcome,
                "outcome_label": OUTCOME_LABELS.get(h.outcome or ""),
                "note": h.note,
            }
            for h in (*scheduled, *done)
        ]
    }
