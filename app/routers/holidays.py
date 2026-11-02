import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import CurrentUser, DbSession, Paging
from app.core.errors import ERROR_RESPONSES, ErrorResponse
from app.schemas import Page
from app.schemas import HolidayCreate, HolidayOut
from app.services import holiday_service

router = APIRouter(prefix="/holidays", tags=["Holidays"], responses=ERROR_RESPONSES)


@router.get(
    "", response_model=Page[HolidayOut], summary="Your holidays plus the global list (read only)"
)
def list_holidays(
    user: CurrentUser,
    db: DbSession,
    page: Paging,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
):
    return holiday_service.list_holidays(db, user, year, page)


@router.post(
    "",
    response_model=HolidayOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse, "description": "Date already listed"}},
)
def add_holiday(body: HolidayCreate, user: CurrentUser, db: DbSession):
    return holiday_service.add_holiday(db, user, body)


@router.delete(
    "/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete your own holiday"
)
def delete_holiday(holiday_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    holiday_service.delete_holiday(db, user, holiday_id)
