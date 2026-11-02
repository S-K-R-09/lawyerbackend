import calendar as cal
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import today_in
from app.models import Case, CaseDeadline, Hearing, User

ATTENTION_DEADLINE_LIMIT = 20


def today_screen(db: Session, user: User) -> dict:
    today = today_in(user.timezone)

    rows = db.execute(
        select(Hearing, Case)
        .join(Case, Case.id == Hearing.case_id)
        .where(
            Hearing.owner_id == user.id,
            Hearing.hearing_date == today,
            Hearing.status == "scheduled",
            Case.deleted_at.is_(None),
        )
        .order_by(
            Hearing.hearing_time.asc().nulls_last(),
            Hearing.created_at,
            Hearing.id,
        )
    ).all()

    next_up = None
    later = []

    for i, (h, c) in enumerate(rows):
        if i == 0:
            next_up = {
                "hearing_id": h.id,
                "time": h.hearing_time,
                "case_id": c.id,
                "case_title": c.title,
                "court": c.court,
                "court_room": c.court_room,
                "purpose": h.purpose,
            }
        else:
            later.append(
                {
                    "hearing_id": h.id,
                    "case_id": c.id,
                    "time": h.hearing_time,
                    "case_title": c.title,
                    "court": c.court,
                    "purpose": h.purpose,
                }
            )

    dls = db.execute(
        select(CaseDeadline, Case)
        .join(Case, Case.id == CaseDeadline.case_id)
        .where(
            CaseDeadline.owner_id == user.id,
            CaseDeadline.status == "active",
            Case.deleted_at.is_(None),
        )
        .order_by(CaseDeadline.last_date, CaseDeadline.id)
        .limit(ATTENTION_DEADLINE_LIMIT)
    ).all()

    return {
        "date": today,
        "next_up": next_up,
        "later_today": later,
        "attention": {
            "deadlines": [
                {
                    "case_id": c.id,
                    "case_title": c.title,
                    "last_date": d.last_date,
                    "days_left": (d.last_date - today).days,
                }
                for d, c in dls
            ],
        },
    }


def month_dots(db: Session, user: User, month: str) -> list[dict]:
    year, mon = (int(x) for x in month.split("-"))

    first = dt.date(year, mon, 1)
    last = dt.date(year, mon, cal.monthrange(year, mon)[1])

    rows = db.execute(
        select(Hearing.hearing_date, func.count())
        .join(Case, Case.id == Hearing.case_id)
        .where(
            Hearing.owner_id == user.id,
            Hearing.hearing_date.between(first, last),
            Case.deleted_at.is_(None),
        )
        .group_by(Hearing.hearing_date)
        .order_by(Hearing.hearing_date)
    ).all()

    return [{"date": d, "hearing_count": n} for d, n in rows]