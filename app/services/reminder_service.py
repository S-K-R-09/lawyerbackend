import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import get_tz, now_utc, today_in
from app.models import Case
from app.models import Hearing
from app.models import CaseDeadline
from app.models import User
from app.services.user_service import get_settings_row


def upcoming(db: Session, user: User, days: int) -> list[dict]:
    """remind_at is pre-computed in the lawyer's timezone; the app just schedules notifications."""
    cfg = get_settings_row(db, user)
    tz = get_tz(user.timezone)
    now = now_utc()
    today = today_in(user.timezone)
    horizon = now + dt.timedelta(days=days)
    out: list[dict] = []

    def at(day: dt.date) -> dt.datetime:
        return dt.datetime.combine(day, cfg.hearing_reminder_time, tzinfo=tz)

    if cfg.hearing_reminder_enabled:
        rows = db.execute(
            select(Hearing, Case)
            .join(Case, Case.id == Hearing.case_id)
            .where(
                Hearing.owner_id == user.id,
                Hearing.status == "scheduled",
                Hearing.hearing_date >= today,
                Hearing.hearing_date <= today + dt.timedelta(days=days + 1),
                Case.deleted_at.is_(None),
            )
        ).all()
        for h, c in rows:
            remind = at(h.hearing_date - dt.timedelta(days=1))  # the evening before
            if now <= remind <= horizon:
                out.append(
                    {
                        "type": "hearing",
                        "case_id": c.id,
                        "title": c.title,
                        "event_date": h.hearing_date,
                        "remind_at": remind,
                    }
                )

    if cfg.deadline_reminder_enabled:
        lead = cfg.deadline_reminder_days
        rows = db.execute(
            select(CaseDeadline, Case)
            .join(Case, Case.id == CaseDeadline.case_id)
            .where(
                CaseDeadline.owner_id == user.id,
                CaseDeadline.status == "active",
                CaseDeadline.last_date >= today,
                CaseDeadline.last_date <= today + dt.timedelta(days=days + lead),
                Case.deleted_at.is_(None),
            )
        ).all()
        for d, c in rows:
            remind = at(d.last_date - dt.timedelta(days=lead))
            if remind < now:
                # Lead window already open: nudge at the next reminder time, up to the last date.
                remind = at(today) if at(today) >= now else at(today + dt.timedelta(days=1))
                if remind.date() > d.last_date:
                    continue
            if remind <= horizon:
                out.append(
                    {
                        "type": "deadline",
                        "case_id": c.id,
                        "title": c.title,
                        "event_date": d.last_date,
                        "remind_at": remind,
                    }
                )
    out.sort(key=lambda r: (r["remind_at"], r["type"]))
    return out
