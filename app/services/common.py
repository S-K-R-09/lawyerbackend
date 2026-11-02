"""Owner-scoped lookups. Missing OR owned-by-someone-else both raise 404."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models import (
    Case,
    CaseDeadline,
    Client,
    Hearing,
    User,
)


def like_pattern(term: str) -> str:
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def count(db: Session, stmt: Any) -> int:
    return db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0


def get_owned_client(db: Session, user: User, client_id: uuid.UUID) -> Client:
    obj = db.scalar(
        select(Client).where(
            Client.id == client_id,
            Client.owner_id == user.id,
            Client.deleted_at.is_(None),
        )
    )
    if obj is None:
        raise not_found("Client not found.")
    return obj


def get_owned_case(
    db: Session, user: User, case_id: uuid.UUID, lock: bool = False
) -> Case:
    stmt = select(Case).where(
        Case.id == case_id,
        Case.owner_id == user.id,
        Case.deleted_at.is_(None),
    )
    if lock:
        stmt = stmt.with_for_update()

    obj = db.scalar(stmt)
    if obj is None:
        raise not_found("Case not found.")
    return obj


def get_owned_hearing(
    db: Session, user: User, hearing_id: uuid.UUID, lock: bool = False
) -> Hearing:
    stmt = (
        select(Hearing)
        .join(Case, Case.id == Hearing.case_id)
        .where(
            Hearing.id == hearing_id,
            Hearing.owner_id == user.id,
            Case.deleted_at.is_(None),
        )
    )
    if lock:
        stmt = stmt.with_for_update(of=Hearing)

    obj = db.scalar(stmt)
    if obj is None:
        raise not_found("Hearing not found.")
    return obj


def get_owned_deadline(
    db: Session, user: User, deadline_id: uuid.UUID
) -> CaseDeadline:
    obj = db.scalar(
        select(CaseDeadline)
        .join(Case, Case.id == CaseDeadline.case_id)
        .where(
            CaseDeadline.id == deadline_id,
            CaseDeadline.owner_id == user.id,
            Case.deleted_at.is_(None),
        )
    )
    if obj is None:
        raise not_found("Deadline not found.")
    return obj