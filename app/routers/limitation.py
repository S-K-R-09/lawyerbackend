import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Paging
from app.core.errors import ERROR_RESPONSES
from app.schemas import Page
from app.schemas import (
    CalculateIn,
    CalculateOut,
    DeadlineCreate,
    DeadlineOut,
    DeadlineUpdate,
    RuleOut,
)
from app.services import limitation_service

router = APIRouter(tags=["Limitation"], responses=ERROR_RESPONSES)


@router.get(
    "/limitation/rules",
    response_model=list[RuleOut],
    summary="Rules for the calculator. `trigger_label` names the date field. Helper values only",
)
def rules(user: CurrentUser, db: DbSession):
    return limitation_service.list_rules(db)


@router.post(
    "/limitation/calculate",
    response_model=CalculateOut,
    summary="Calculate a last date (nothing is saved). A helper, not legal advice",
    description=(
        "Trigger day excluded; days added directly; months/years via calendar arithmetic "
        "(month ends clamp); Sundays and holidays (global + your own) roll forward. "
        "Certified-copy time exclusion and special exemptions are **not** applied (out of MVP)."
    ),
)
def calculate(body: CalculateIn, user: CurrentUser, db: DbSession):
    return limitation_service.calculate(db, user, body)


@router.post(
    "/cases/{case_id}/deadlines",
    response_model=DeadlineOut,
    status_code=201,
    summary="Save a deadline to a case (recomputed on the server, never trusting client dates)",
)
def save_deadline(case_id: uuid.UUID, body: DeadlineCreate, user: CurrentUser, db: DbSession):
    return limitation_service.save_deadline(db, user, case_id, body)


@router.get(
    "/cases/{case_id}/deadlines", response_model=Page[DeadlineOut], summary="Deadlines of one case"
)
def case_deadlines(
    case_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    page: Paging,
    status: Literal["active", "done", "dismissed", "all"] = "active",
):
    return limitation_service.list_deadlines(db, user, status, page, case_id)


@router.get(
    "/deadlines", response_model=Page[DeadlineOut], summary="All deadlines, ordered by last date"
)
def deadlines(
    user: CurrentUser,
    db: DbSession,
    page: Paging,
    status: Annotated[Literal["active", "done", "dismissed", "all"], Query()] = "active",
):
    return limitation_service.list_deadlines(db, user, status, page)


@router.patch(
    "/deadlines/{deadline_id}", response_model=DeadlineOut, summary="Mark done or dismiss"
)
def patch_deadline(deadline_id: uuid.UUID, body: DeadlineUpdate, user: CurrentUser, db: DbSession):
    return limitation_service.update_deadline(db, user, deadline_id, body)
