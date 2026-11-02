import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import Pagination
from app.core.errors import conflict
from app.models import Case
from app.models import Client
from app.models import User
from app.schemas import ClientCreate, ClientUpdate
from app.services.common import count, get_owned_client, like_pattern

DUP_PHONE = "You already have a client with this phone number."


def _check_phone_free(
    db: Session, user: User, phone: str, exclude: uuid.UUID | None = None
) -> None:
    stmt = select(Client.id).where(
        Client.owner_id == user.id, Client.phone == phone, Client.deleted_at.is_(None)
    )
    if exclude:
        stmt = stmt.where(Client.id != exclude)
    if db.scalar(stmt):
        raise conflict(DUP_PHONE, {"phone": "Already used by another client."})


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict(DUP_PHONE, {"phone": "Already used by another client."}) from exc


def list_clients(db: Session, user: User, q: str | None, page: Pagination):
    base = select(Client).where(Client.owner_id == user.id, Client.deleted_at.is_(None))
    if q and q.strip():
        pat = like_pattern(q)
        base = base.where(
            or_(Client.name.ilike(pat, escape="\\"), Client.phone.ilike(pat, escape="\\"))
        )
    total = count(db, base)
    rows = list(
        db.scalars(
            base.order_by(func.lower(Client.name), Client.id).limit(page.limit).offset(page.offset)
        )
    )
    ids = [c.id for c in rows]
    counts: dict[uuid.UUID, int] = {}
    latest: dict[uuid.UUID, str] = {}
    if ids:  # two grouped queries for the whole page: no N+1
        live = (Case.owner_id == user.id, Case.deleted_at.is_(None), Case.client_id.in_(ids))
        counts = dict(
            db.execute(
                select(Case.client_id, func.count()).where(*live).group_by(Case.client_id)
            ).all()
        )
        for case in db.scalars(
            select(Case)
            .where(*live)
            .distinct(Case.client_id)
            .order_by(Case.client_id, Case.created_at.desc())
        ):
            latest[case.client_id] = case.title
    items = [
        {
            "id": c.id,
            "name": c.name,
            "phone": c.phone,
            "cases_count": counts.get(c.id, 0),
            "latest_case_title": latest.get(c.id),
        }
        for c in rows
    ]
    return {"items": items, "total": total, "limit": page.limit, "offset": page.offset}


def create_client(db: Session, user: User, data: ClientCreate) -> Client:
    _check_phone_free(db, user, data.phone)
    client = Client(owner_id=user.id, **data.model_dump())
    db.add(client)
    _commit(db)
    return client


def client_detail(db: Session, user: User, client_id: uuid.UUID) -> dict:
    client = get_owned_client(db, user, client_id)
    cases = db.scalars(
        select(Case)
        .where(Case.owner_id == user.id, Case.client_id == client.id, Case.deleted_at.is_(None))
        .order_by(Case.created_at.desc())
    )
    return {
        "id": client.id,
        "name": client.name,
        "phone": client.phone,
        "email": client.email,
        "address": client.address,
        "cases": [
            {
                "id": c.id,
                "title": c.title,
                "case_number": c.case_number,
                "status": c.status,
                "stage": c.stage,
                "next_hearing_date": c.next_hearing_date,
            }
            for c in cases
        ],
    }


def update_client(db: Session, user: User, client_id: uuid.UUID, data: ClientUpdate) -> Client:
    client = get_owned_client(db, user, client_id)
    changes = data.model_dump(exclude_unset=True)
    for required in ("name", "phone"):
        if changes.get(required) is None:
            changes.pop(required, None)
    if "phone" in changes and changes["phone"] != client.phone:
        _check_phone_free(db, user, changes["phone"], exclude=client.id)
    for k, v in changes.items():
        setattr(client, k, v)
    _commit(db)
    return client


def delete_client(db: Session, user: User, client_id: uuid.UUID) -> None:
    client = get_owned_client(db, user, client_id)
    open_cases = (
        db.scalar(
            select(func.count()).where(
                Case.owner_id == user.id,
                Case.client_id == client.id,
                Case.deleted_at.is_(None),
                Case.status == "open",
            )
        )
        or 0
    )
    if open_cases:
        raise conflict(
            f"This client has {open_cases} open case{'s' if open_cases != 1 else ''}. "
            "Close or delete them before removing the client."
        )
    client.deleted_at = func.now()
    db.commit()
