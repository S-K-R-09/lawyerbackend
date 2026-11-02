import uuid

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import today_in
from app.core.deps import Pagination
from app.core.errors import conflict
from app.models import (
    Case,
    CaseDeadline,
    Client,
    Hearing,
    LimitationRule,
    User,
)
from app.schemas import CaseCreate, CaseUpdate
from app.services.common import count, get_owned_case, get_owned_client, like_pattern

DUP_CASE = "A case with this number already exists in this court."


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict(DUP_CASE, {"case_number": "Already exists for this court."}) from exc


def _check_unique(db: Session, user: User, court: str, number: str, exclude=None) -> None:
    stmt = select(Case.id).where(
        Case.owner_id == user.id,
        Case.court == court,
        Case.case_number == number,
        Case.deleted_at.is_(None),
    )
    if exclude:
        stmt = stmt.where(Case.id != exclude)
    if db.scalar(stmt):
        raise conflict(DUP_CASE, {"case_number": "Already exists for this court."})


def list_cases(db: Session, user: User, status: str, q: str | None, page: Pagination) -> dict:
    base = (
        select(Case)
        .join(Client, Client.id == Case.client_id)
        .where(Case.owner_id == user.id, Case.deleted_at.is_(None))
    )
    if q and q.strip():
        pat = like_pattern(q)
        base = base.where(
            or_(
                *(
                    col.ilike(pat, escape="\\")
                    for col in (
                        Case.case_number,
                        Case.petitioner,
                        Case.respondent,
                        Case.court,
                        Client.name,
                    )
                )
            )
        )

    sub = base.subquery()
    by_status = dict(db.execute(select(sub.c.status, func.count()).group_by(sub.c.status)).all())

    meta = {
        "active": by_status.get("open", 0),
        "closed": by_status.get("closed", 0),
        "all": sum(by_status.values()),
    }

    if status in ("active", "open"):
        base = base.where(Case.status == "open")
    elif status == "closed":
        base = base.where(Case.status == "closed")

    total = count(db, base)

    has_deadline = exists(
        select(1).where(
            CaseDeadline.case_id == Case.id,
            CaseDeadline.status == "active",
        )
    ).label("has_active_deadline")

    rows = db.execute(
        base.add_columns(has_deadline)
        .order_by(
            Case.next_hearing_date.asc().nulls_last(),
            Case.created_at.desc(),
            Case.id,
        )
        .limit(page.limit)
        .offset(page.offset)
    ).all()

    items = [
        {
            "id": c.id,
            "title": c.title,
            "case_number": c.case_number,
            "court": c.court,
            "status": c.status,
            "stage": c.stage,
            "next_hearing_date": c.next_hearing_date,
            "has_active_deadline": bool(flag),
        }
        for c, flag in rows
    ]

    return {
        "items": items,
        "total": total,
        "limit": page.limit,
        "offset": page.offset,
        "meta": meta,
    }


def create_case(db: Session, user: User, data: CaseCreate) -> dict:
    get_owned_client(db, user, data.client_id)
    _check_unique(db, user, data.court, data.case_number)

    case = Case(owner_id=user.id, **data.model_dump())
    db.add(case)
    _commit(db)

    return case_detail(db, user, case.id)


def update_case(db: Session, user: User, case_id: uuid.UUID, data: CaseUpdate) -> dict:
    case = get_owned_case(db, user, case_id, lock=True)

    changes = data.model_dump(exclude_unset=True)

    for required in ("client_id", "case_number", "court", "case_type", "status"):
        if changes.get(required) is None:
            changes.pop(required, None)

    if "client_id" in changes:
        get_owned_client(db, user, changes["client_id"])

    new_court = changes.get("court", case.court)
    new_number = changes.get("case_number", case.case_number)

    if (new_court, new_number) != (case.court, case.case_number):
        _check_unique(db, user, new_court, new_number, exclude=case.id)

    new_status = changes.pop("status", None)

    for k, v in changes.items():
        setattr(case, k, v)

    if new_status is not None and new_status != case.status:
        case.status = new_status
        case.closed_on = today_in(user.timezone) if new_status == "closed" else None

    _commit(db)

    return case_detail(db, user, case.id)


def delete_case(db: Session, user: User, case_id: uuid.UUID) -> None:
    case = get_owned_case(db, user, case_id, lock=True)
    case.deleted_at = func.now()
    db.commit()


def case_detail(db: Session, user: User, case_id: uuid.UUID) -> dict:
    case = get_owned_case(db, user, case_id)
    today = today_in(user.timezone)

    client = db.get(Client, case.client_id)

    nxt = db.scalar(
        select(Hearing)
        .where(
            Hearing.case_id == case.id,
            Hearing.owner_id == user.id,
            Hearing.status == "scheduled",
            Hearing.hearing_date >= today,
        )
        .order_by(
            Hearing.hearing_date,
            Hearing.hearing_time.asc().nulls_last(),
        )
        .limit(1)
    )

    dl = db.execute(
        select(CaseDeadline, LimitationRule.label)
        .join(LimitationRule, LimitationRule.id == CaseDeadline.rule_id)
        .where(
            CaseDeadline.case_id == case.id,
            CaseDeadline.owner_id == user.id,
            CaseDeadline.status == "active",
        )
        .order_by(CaseDeadline.last_date)
        .limit(1)
    ).first()

    def _n(model, *extra) -> int:
        return (
            db.scalar(
                select(func.count()).where(
                    model.case_id == case.id,
                    model.owner_id == user.id,
                    *extra,
                )
            )
            or 0
        )

    return {
        "id": case.id,
        "title": case.title,
        "case_number": case.case_number,
        "court": case.court,
        "court_room": case.court_room,
        "case_type": case.case_type,
        "status": case.status,
        "stage": case.stage,
        "petitioner": case.petitioner,
        "respondent": case.respondent,
        "notes": case.notes,
        "closed_on": case.closed_on,
        "client": {
            "id": client.id,
            "name": client.name,
            "phone": client.phone,
        },
        "next_hearing": (
            {
                "hearing_id": nxt.id,
                "hearing_date": nxt.hearing_date,
                "hearing_time": nxt.hearing_time,
                "purpose": nxt.purpose,
            }
            if nxt
            else None
        ),
        "active_deadline": (
            {
                "id": dl[0].id,
                "label": dl[1],
                "last_date": dl[0].last_date,
                "days_left": (dl[0].last_date - today).days,
            }
            if dl
            else None
        ),
        "counts": {
            "hearings": _n(Hearing),
            "deadlines": _n(CaseDeadline, CaseDeadline.status == "active"),
        },
    }