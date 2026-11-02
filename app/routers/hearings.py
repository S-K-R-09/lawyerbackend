import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, Paging
from app.core.errors import ERROR_RESPONSES, ErrorResponse
from app.schemas import Page
from app.schemas import (
    DayHearing,
    HearingOut,
    HearingUpdate,
    RecordHearingIn,
    RecordHearingOut,
)
from app.services import hearing_service

router = APIRouter(prefix="/hearings", tags=["Hearings"], responses=ERROR_RESPONSES)


@router.get(
    "", response_model=Page[DayHearing], summary="Hearings of one day (list under the calendar)"
)
def hearings_on_date(
    user: CurrentUser,
    db: DbSession,
    page: Paging,
    date: Annotated[dt.date, Query(description="YYYY-MM-DD")],
):
    return hearing_service.hearings_on(db, user, date, page)


@router.post(
    "/{hearing_id}/record",
    response_model=RecordHearingOut,
    summary="Record outcome; optionally schedules the next hearing, atomically",
    responses={
        409: {"model": ErrorResponse, "description": "Already recorded"},
    },
)
def record_hearing(hearing_id: uuid.UUID, body: RecordHearingIn, user: CurrentUser, db: DbSession):
    return hearing_service.record_hearing(db, user, hearing_id, body)


@router.patch("/{hearing_id}", response_model=HearingOut, summary="Fix hearing details")
def patch_hearing(hearing_id: uuid.UUID, body: HearingUpdate, user: CurrentUser, db: DbSession):
    return hearing_service.update_hearing(db, user, hearing_id, body)


@router.delete(
    "/{hearing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a mistaken hearing (next_hearing_date is recomputed)",
)
def delete_hearing(hearing_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    hearing_service.delete_hearing(db, user, hearing_id)
