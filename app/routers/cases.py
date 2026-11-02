import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, Paging
from app.core.errors import ERROR_RESPONSES, ErrorResponse
from app.schemas import CaseCreate, CaseDetail, CaseListOut, CaseUpdate, StatusFilter
from app.schemas import HearingCreate, HearingOut, Timeline
from app.services import case_service, hearing_service

router = APIRouter(prefix="/cases", tags=["Cases"], responses=ERROR_RESPONSES)
DUP = {409: {"model": ErrorResponse, "description": "Case number already exists in this court"}}


@router.get(
    "",
    response_model=CaseListOut,
    summary="Cases list. `meta` carries counts for the tabs and the '9 active' subtitle",
)
def list_cases(
    user: CurrentUser,
    db: DbSession,
    page: Paging,
    status_: Annotated[StatusFilter, Query(alias="status")] = "active",
    q: Annotated[
        str | None, Query(max_length=100, description="Case no., parties, court, client")
    ] = None,
):
    return case_service.list_cases(db, user, status_, q, page)


@router.post("", response_model=CaseDetail, status_code=status.HTTP_201_CREATED, responses=DUP)
def create_case(body: CaseCreate, user: CurrentUser, db: DbSession):
    return case_service.create_case(db, user, body)


@router.get("/{case_id}", response_model=CaseDetail, summary="Case detail screen")
def get_case(case_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return case_service.case_detail(db, user, case_id)


@router.patch(
    "/{case_id}",
    response_model=CaseDetail,
    summary="Edit fields, change stage, close/reopen (`status`), notes, agreed fee",
    responses=DUP,
)
def patch_case(case_id: uuid.UUID, body: CaseUpdate, user: CurrentUser, db: DbSession):
    return case_service.update_case(db, user, case_id, body)


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Soft delete")
def delete_case(case_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    case_service.delete_case(db, user, case_id)


@router.get(
    "/{case_id}/timeline",
    tags=["Hearings"],
    response_model=Timeline,
    summary="Next scheduled hearing first, then completed hearings newest first",
)
def case_timeline(case_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return hearing_service.timeline(db, user, case_id)


@router.post(
    "/{case_id}/hearings",
    tags=["Hearings"],
    response_model=HearingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule a hearing (sets or refreshes next_hearing_date)",
)
def schedule_hearing(case_id: uuid.UUID, body: HearingCreate, user: CurrentUser, db: DbSession):
    return hearing_service.schedule_hearing(db, user, case_id, body)
